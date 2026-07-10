#!/usr/bin/env python3
#
# click_n_fly4 = click_n_fly2 (scenario picker, persistent drone pool,
# live telemetry, chronograms, battery display...) + the APF reactive
# avoidance layer, for evaluating the avoidance before adopting it in
# the final unified application.
#
import sys, time, signal, logging, yaml, argparse
import numpy as np
from enum import Enum

from PySide6.QtWidgets import QApplication, QMainWindow, QDialog
from PySide6.QtCore import QRunnable, QThreadPool, QTimer, Slot, Qt
from PySide6.QtGui import QGuiApplication
QGuiApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
# https://www.pythonguis.com/tutorials/multithreading-pyside6-applications-qthreadpool/

import traj_factory, misc_utils as mu
import view_three_d as vtd, model
import scenarios as cnf_scen
import pat3.algebra as p_al

from pprz_connect import PprzConnect
from pprzlink.message import PprzMessage
from settings import PprzSettingsManager
from guided_mode import GuidedMode
from operator_window import OperatorWindow
from scenario_picker import ScenarioPickerDialog
from reactive_avoidance import ReactiveAvoidance

logger = logging.getLogger(__name__)

# Show starts once every drone is within this distance (m) of its start
# point. Larger = starts reliably but with a visible correction jump at
# launch; smaller = cleaner start but hover jitter may prevent it from
# ever triggering. History: v1 used 0.1, v3 uses 0.15.
DIST_TO_START_THRESHOLD = 0.3

# --- Reactive avoidance tuning (see reactive_avoidance.py) -------------
# Field verdict after the sim tuning campaign: the ORIGINAL configuration
# behaves best. Its early bad reputation (references coasting far away,
# blow-ups at show wrap) turned out to be trajectory bugs since fixed
# (unclosed circle_with_intro loops teleporting at wrap, quintic spline
# flailing on the open race track/slalom) rather than the tuning itself.
# The guards added during the campaign (dp_max cap, zeta, d_min) remain
# available below for future experiments.
AVOID_D0       = 1.5   # m, repulsion trigger distance
AVOID_D_MIN    = 0.4   # m, center-to-center distance of full repulsion
AVOID_K_MAX    = 6.0   # m/s2, max repulsive accel
AVOID_TAU      = 1.2   # s, closest-approach prediction horizon
AVOID_ZETA     = 2.0   # 1/s, return stiffness of the deformation spring
AVOID_Z_WEIGHT = 1.0   # 1 = full vertical pushes allowed
AVOID_DP_MAX   = None  # m, hard cap on reference deformation (None = uncapped)
# Deformed references are clamped inside these bounds. Trajectories are
# designed within +/-3m (obstacles near the cage); leave 0.5m of headroom
# for the avoidance to push into, still inside the nominal safe zone.
AVOID_BOUNDS = ((-3.5, 3.5), (-3.5, 3.5), (1., 7.))


class MainWindow(QMainWindow):
    def __init__(self, model, ids, controller):
        super().__init__()
        self.controller = controller
        self.resize(1280,900)
        self.tdw = vtd.ThreeDWidget()
        for i in range(len(ids)):
            # spectator view: show only the real drone. Hide the reference
            # path and the reference ("ghost") quad so the choreography
            # isn't revealed to the audience in advance
            self.tdw.display_new_trajectory(model, i, show_details=False, show_quad=True,
                                            show_ref_quad=False, show_ref_traj=False)
        self.setCentralWidget(self.tdw)

    def set_quad_pose(self, T, i): self.tdw.set_quad_pose(T, i)
    def set_ref_pose(self, T, i): self.tdw.set_ref_pose(T, i)
    def update_vehicle_traj(self, vehicle_traj, i): self.tdw.update_vehicle_traj(vehicle_traj, i)

    def closeEvent(self, event):
        logger.debug('x button clicked')
        self.controller.on_quit()
        event.accept()


DroneStatus = Enum('DroneStatus', [('UNKNOWN', 1), ('CONNECTED', 2), ('READY', 3), ('CRUISING', 4), ('ARRIVED', 5)])
class Drone:
    def __init__(self):
        self.T, self.Tref = [np.eye(4)]*2
        self.Y, self.Yref = [np.zeros((4,5))]*2
        self.vehicle_traj = []
        self.vehicle_traj_max_len, self.vehicle_traj_increment = 1000, 100
        self.status = DroneStatus.UNKNOWN
        self.battery_v = None
        self.link_down = False   # True once an Ivy send has failed (bus gone)

    def connect(self, conf, ivy):
        self.conf = conf
        self.settings = PprzSettingsManager(conf.settings, conf.id, ivy)
        self.guided = GuidedMode(ivy)
        self.status = DroneStatus.CONNECTED

    def _send(self, action):
        """Run an Ivy-sending command; if the bus is gone, degrade
        gracefully (log once) instead of spamming tracebacks. Returns
        True on success, False if the Ivy link is down."""
        try:
            action()
        except RuntimeError as e:
            if not self.link_down:
                _id = getattr(self.conf, 'id', '?')
                logger.warning(f'aircraft {_id}: Ivy link down, command dropped ({e})')
            self.link_down = True
            return False
        self.link_down = False
        return True

    def take_control(self):
        if self.status == DroneStatus.UNKNOWN:
            return True
        def _do():
            self.settings['auto2'] = 'Guided'
            self.guided.move_at_ned_vel(self.conf.id) # set zero speed
        return self._send(_do)

    def release(self):
        if self.status == DroneStatus.UNKNOWN:
            return True
        return self._send(lambda: self.settings.__setitem__('auto2', 'Nav'))

    def set_pose(self, T):
        self.T=T
        self.vehicle_traj.append(mu.pos_of_T(T)) # FIXME: limit size
        if len(self.vehicle_traj) > self.vehicle_traj_max_len:
            self.vehicle_traj = self.vehicle_traj[self.vehicle_traj_increment:]


    def set_ref(self, Tref, Yref): self.Tref, self.Yref = Tref, Yref
    def goto_ref(self):
        return self._send(lambda: self.guided.goto_enu(self.conf.id, *self.Yref[:,0]))
    def follow_ref(self):
        Y = mu.Yenu2ned(self.Yref)
        return self._send(lambda: self.guided.set_full_ned(self.conf.id,
                                 Y[0,0], Y[1,0], Y[2,0],
                                 Y[0,1], Y[1,1], Y[2,1],
                                 Y[0,2], Y[1,2], Y[2,2],
                                 Y[3,0]))

    def dist_to_ref(self):
        return np.linalg.norm(mu.pos_of_T(self.T)-mu.pos_of_T(self.Tref))

FDStatus = Enum('FDStatus', [('STAGING', 1), ('GETTING_READY', 2), ('GUIDING', 3), ('FINISHED', 4)])
class FlightDirector:
    def __init__(self, trajectories, ids):
        self.trajectories = trajectories
        self.pprz_connect = PprzConnect(notify=self.on_pprz_connect)
        self.pprz_connect.ivy.subscribe(self.on_pprz_flight_param, PprzMessage("telemetry", "ROTORCRAFT_FP"))
        self.pprz_connect.ivy.subscribe(self.on_pprz_external_pose, PprzMessage("datalink", "EXTERNAL_POSE"))
        self.pprz_connect.ivy.subscribe(self.on_pprz_status, PprzMessage("telemetry", "ROTORCRAFT_STATUS"))
        self.status = FDStatus.STAGING
        self.ids, self.acs = ids, {}
        for _id in self.ids:
            self.acs[_id] = Drone()
        # Persistent pool: keep a strong reference to every Drone ever created,
        # even ids not in the current scenario. Dropping a Drone would let
        # Python garbage-collect its Ivy-bound settings/guided objects, which
        # tears down the shared Ivy bus ("Ivy server not running!") after a
        # scenario switch that removes a drone.
        self.drone_pool = dict(self.acs)
        self.known_confs = {}  # every conf ever seen, even for ids not currently in acs
        self.t0 = 0.
        self.duree_du_show = self.trajectories.trajectory_duration()  #POur avoir la durée du show
        # reactive deconfliction: deforms the references away from measured
        # conflicts (APF repulsion) while the show is flying
        self.avoider = ReactiveAvoidance(d0=AVOID_D0, d_min=AVOID_D_MIN, k_max=AVOID_K_MAX,
                                         tau=AVOID_TAU, zeta=AVOID_ZETA,
                                         z_weight=AVOID_Z_WEIGHT, dp_max=AVOID_DP_MAX,
                                         mode='deform', bounds=AVOID_BOUNDS)

    def on_pprz_external_pose(self, sender, msg):
        pos_enu = [msg[_c] for _c in ['enu_x', 'enu_y', 'enu_z']]
        quat = np.array([msg[_c] for _c in ['body_qi', 'body_qx', 'body_qy', 'body_qz']])
        rmat_enu2flu = p_al.rmat_of_quat(quat)
        T = np.eye(4); T[:3,3] = pos_enu; T[:3,:3] = rmat_enu2flu
        try:
            ac = self.acs[int(sender)]
        except KeyError: return # unknown
        ac.pose_source = 'external'
        ac.set_pose(T)

    def run(self): # for now called from GUI thread, maybe use our own thread?
        if self.status == FDStatus.STAGING or self.status == FDStatus.GETTING_READY:
            elapsed = 0.
        else:
            elapsed = time.time() - self.t0
        if self.status == FDStatus.GUIDING:
            elapsed = elapsed % self.duree_du_show

        # compute nominal references, and collect measured positions of the
        # drones whose pose we have actually received
        Yrefs, positions = {}, {}
        for idx_traj, id_ac in enumerate(self.ids):
            Yrefs[id_ac] = self.trajectories.get_trajectory(idx_traj).get(elapsed)
            ac = self.acs[id_ac]
            if ac.vehicle_traj:
                positions[id_ac] = mu.pos_of_T(ac.T)

        # reactive deconfliction, only while actually flying the show
        if self.status == FDStatus.GUIDING:
            now = time.time()
            dt = min(now - getattr(self, '_t_avoid', now), 0.2)  # clamp dt spikes
            self._t_avoid = now
            self.avoider.apply(self.ids, Yrefs, positions, dt)

        for id_ac in self.ids:
            Yref = Yrefs[id_ac]
            Tref = np.eye(4); Tref[:3,3] = Yref[:3,0]
            self.acs[id_ac].set_ref(Tref, Yref)

        drone_status = [self.acs[_id].status for _id in self.ids]
        if self.status == FDStatus.STAGING:
            if np.all([s == DroneStatus.CONNECTED for s in drone_status]):
                self.status = FDStatus.GETTING_READY
                for i in self.ids:
                  self.acs[i].goto_ref()
                logger.debug('all drones connected, moving them to start pos')
        elif self.status == FDStatus.GETTING_READY:
            dist_to_start = [self.acs[i].dist_to_ref() for i in self.ids]
            if np.max(dist_to_start) < DIST_TO_START_THRESHOLD:
                self.duree_du_show = self.trajectories.trajectory_duration()
                self.status, self.t0 = FDStatus.GUIDING, time.time()
                logger.debug('all drones arrived to start, starting the show')
        elif self.status == FDStatus.GUIDING:
            for i in self.ids:
                self.acs[i].follow_ref()
        elif self.status == FDStatus.FINISHED:
            pass

    def on_pprz_connect(self, conf):
        logger.debug(f'{conf.id} ({conf.name}) connected')
        self.known_confs[int(conf.id)] = conf
        if int(conf.id) in self.acs:
            self.acs[int(conf.id)].connect(conf, self.pprz_connect.ivy)
            self.acs[int(conf.id)].take_control()

    def on_pprz_flight_param(self, sender, msg):
        pos_enu = [float(msg[_c])/2**8 for _c in ['east', 'north', 'up']]
        euler_ned2frd = [float(msg[_c])/2**12 for _c in ['phi', 'theta', 'psi']]
        rmat_enu2flu = mu.rmat_enu2flu_of_euler_ned2frd(euler_ned2frd)
        T = np.eye(4); T[:3,3] = pos_enu; T[:3,:3] = rmat_enu2flu
        try:
            ac = self.acs[sender]
        except KeyError: return # unknown aircraft
        if getattr(ac, 'pose_source', None) == 'external':
            return
        ac.set_pose(T)

    def on_pprz_status(self, sender, msg):
        try:
            ac = self.acs[sender]
        except KeyError: return # unknown aircraft
        ac.battery_v = float(msg['vsupply'])

    def get_acs(self): return self.acs
    def quit(self):
        # release every drone ever pooled, not just the active scenario's,
        # so none is left armed in Guided from an earlier scenario
        for drone in self.drone_pool.values():
            drone.release()
        time.sleep(0.2) # wait for message to be transmitted before closing middleware, yeah.. fuck, we need synchro with ivy
        self.pprz_connect.shutdown()



class Application(QApplication):
    def __init__(self, args):
        super().__init__(sys.argv)
        self.setApplicationDisplayName("ClicknFly")
        self.setApplicationName("ClicknFly4")

        picker = ScenarioPickerDialog(cnf_scen.scenarios, preselect=int(args.scen))
        if picker.exec() != QDialog.DialogCode.Accepted:
            sys.exit(0)
        self.scenario = picker.get_scenario()
        trajs, ids = self.scenario.trajs, self.scenario.ids

        self.model = model.Model()
        for traj_name in trajs:
            self.model.load_from_factory(traj_name)

        self.fd = FlightDirector(self.model, ids)
        self.window = MainWindow(self.model, ids, self)
        self.window.setWindowTitle("Click'n Fly 4 - Spectator view")
        self.window.show()

        self.operator_view = OperatorWindow(self, self.model, self.fd)
        self.operator_view.show()
        self.operator_view.log_text(
            f'Reactive avoidance armed: d0={AVOID_D0}m, k_max={AVOID_K_MAX}m/s2, '
            f'tau={AVOID_TAU}s, zeta={AVOID_ZETA}, dp_max={AVOID_DP_MAX}m')

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.periodic)
        self.timer.start(50)
        self.t0, self.dt_control = time.time(), 0.05

        self.is_guiding = False

    def on_quit(self):
        if getattr(self, '_quitting', False):
            return
        self._quitting = True
        logger.debug('app on quit')
        self.fd.quit()
        self.quit()

    def on_guide_clicked(self):
        self.operator_view.log_text('Take off and trajectory following started')
        # start each show with no residual avoidance deformation
        self.fd.avoider.reset()
        # re-arm Guided mode: a no-op for drones connecting for the first
        # time (already armed in on_pprz_connect), but required for drones
        # released to NAV by a previous Stop (e.g. before a scenario switch)
        results = [self.fd.acs[ac_id].take_control() for ac_id in self.fd.ids]
        if not all(results):
            self.operator_view.log_text(
                'WARNING: Ivy bus unavailable - is Paparazzi (server/simulator) running?')
        self.fd.status = FDStatus.STAGING
        self.is_guiding = True
        self.operator_view.button_guide.setEnabled(False)
        self.operator_view.button_stop.setEnabled(True)

    def on_stop_clicked(self):
        self.operator_view.log_text("Show stopped: NAV Mode ")
        self.is_guiding = False
        self.fd.status = FDStatus.FINISHED
        for ac_id in self.fd.ids:
            self.fd.acs[ac_id].release()
        self.operator_view.button_guide.setEnabled(True)
        self.operator_view.button_stop.setEnabled(False)

    def on_change_scenario_clicked(self):
        preselect = 0
        current_name = getattr(self.scenario, "name", None)
        for i, cls in enumerate(cnf_scen.scenarios):
            if cls.__name__ == current_name:
                preselect = i
                break
        picker = ScenarioPickerDialog(cnf_scen.scenarios, preselect=preselect,
                                      parent=self.operator_view)
        if picker.exec() == QDialog.DialogCode.Accepted:
            self._load_scenario(picker.get_scenario())

    def _load_scenario(self, scenario):
        # bring the current show to a safe stop before tearing it down
        if self.is_guiding:
            self.on_stop_clicked()

        self.scenario = scenario
        trajs, ids = scenario.trajs, scenario.ids

        new_model = model.Model()
        for traj_name in trajs:
            new_model.load_from_factory(traj_name)

        # Reuse Drone objects from the persistent pool (never dropped, so their
        # Ivy connection stays alive). A drone new to this run but already seen
        # on the Ivy bus is adopted immediately (its original on_pprz_connect
        # notification was lost since it wasn't tracked yet); a truly new id
        # starts out unconnected.
        new_acs = {}
        for _id in ids:
            drone = self.fd.drone_pool.get(_id)
            if drone is None:
                drone = Drone()
                self.fd.drone_pool[_id] = drone
                conf = self.fd.known_confs.get(_id)
                if conf is not None:
                    drone.connect(conf, self.fd.pprz_connect.ivy)
                    drone.take_control()
            new_acs[_id] = drone
        # drones survive scenario switches (persistent pool), so their flown
        # trace must be cleared explicitly or the old show's trail lingers
        # in the freshly rebuilt 3D views
        for drone in new_acs.values():
            drone.vehicle_traj = []
        self.fd.acs = new_acs
        self.fd.ids = ids
        self.fd.trajectories = new_model
        self.fd.duree_du_show = new_model.trajectory_duration()
        self.fd.status = FDStatus.STAGING
        self.fd.t0 = 0.
        self.fd.avoider.reset()   # no residual deformation from the previous show

        self.model = new_model
        self.window.tdw.set_trajectories(new_model, show_details=False,
                                         show_quad=True, show_ref_quad=False,
                                         show_ref_traj=False)  # spectator: real drone only
        self.operator_view.load_show(new_model, self.fd, scenario)

        name = getattr(scenario, "name", None) or scenario.__class__.__name__
        self.operator_view.log_text(f"Scenario changed: {name}")

    def periodic(self):
        now = time.time()
        elapsed = now - self.t0
        if elapsed >= self.dt_control:
            if self.is_guiding:
                self.fd.run()
                self.operator_view.drones_panel.update_from_fd(self.fd)
            # always record (not only while guiding): staging and manual
            # moves are interesting to see in the live telemetry too
            self.operator_view.record_live_telemetry(self.fd)
            self.t0 += self.dt_control

        if self.is_guiding and self.fd.status == FDStatus.GUIDING:
            loop_elapsed = (time.time() - self.fd.t0) % self.fd.duree_du_show
            progress_percent= int((loop_elapsed / self.fd.duree_du_show) * 100)
            self.operator_view.show_progress(progress_percent)

        acs = self.fd.get_acs()
        for i, ac_id in enumerate(self.fd.ids):
            ac = acs[ac_id]
            self.window.set_ref_pose(ac.Tref, i)
            try:
                self.window.set_quad_pose(ac.T, i)
            except KeyError: pass # we don't know the drone pose yet
            self.window.update_vehicle_traj(np.array(ac.vehicle_traj), i)

            self.operator_view.tdw.set_ref_pose(ac.Tref, i)
            try:
                self.operator_view.tdw.set_quad_pose(ac.T, i)
            except KeyError: pass # we don't know the drone pose yet
            self.operator_view.tdw.update_vehicle_traj(np.array(ac.vehicle_traj), i)


def parse_cli():
    parser = argparse.ArgumentParser(description='ClicknFly 4, flight director with reactive avoidance.')
    parser.add_argument('--scen', help='the name of the scenario', default=0)
    parser.add_argument('--qt-name', help="Set the window name.", default='blaaaa', metavar="inkcut")
    args = parser.parse_args()
    return args


def main():
    logging.basicConfig(level=logging.INFO)
    logger.setLevel(logging.DEBUG)
    args = parse_cli()
    cnf = Application(args)
    def _quit(sig, frame):
        logger.debug('Keyboard interrupt')
        cnf.on_quit()
        sys.exit()
    signal.signal(signal.SIGINT, _quit)
    cnf.exec()


if __name__ == '__main__':
    main()
