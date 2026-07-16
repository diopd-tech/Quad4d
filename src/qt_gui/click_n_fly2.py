#!/usr/bin/env python3
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
import flight_blocks as fb

logger = logging.getLogger(__name__)

# Show starts once every drone is within this distance (m) of its start
# point. Larger = starts reliably but with a visible correction jump at
# launch; smaller = cleaner start but hover jitter may prevent it from
# ever triggering. History: v1 used 0.1, v3 uses 0.15.
DIST_TO_START_THRESHOLD = 0.3


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


# class Worker(QRunnable):
#     def __init__(self, trajectory, traj_manager, dt=1./10):
#         super().__init__()
        
#     @Slot()
#     def run(self):
#         time.sleep(1)
#         print('worker exiting')


DroneStatus = Enum('DroneStatus', [('UNKNOWN', 1), ('CONNECTED', 2), ('READY', 3), ('CRUISING', 4), ('ARRIVED', 5)])
class Drone:
    def __init__(self):
        self.T, self.Tref = [np.eye(4)]*2
        self.Y, self.Yref = [np.zeros((4,5))]*2
        self.vehicle_traj = []
        self.vehicle_traj_max_len, self.vehicle_traj_increment = 1000, 100
        # maybe? https://github.com/eric-wieser/numpy_ringbuffer/blob/master/numpy_ringbuffer/__init__.py
        self.status = DroneStatus.UNKNOWN
        self.battery_v = None
        self.link_down = False   # True once an Ivy send has failed (bus gone)
        # pre-flight checklist inputs (see drones_panel)
        self.t_last_ext_pose = None  # last EXTERNAL_POSE seen (mocap uplink)
        self.t_last_status = None    # last ROTORCRAFT_STATUS (downlink alive)
        self.rc_status = None        # 0 OK, 1 LOST, 2 REALLY_LOST
        self.arming_status = None
        self.blocks = None           # flight plan block table, set on connect
        # flight plan / autopilot state shown in the drones panel
        self.ap_mode = None          # index into the ap_mode values (13 NAV, 19 GUIDED)
        self.ap_motors_on = None
        self.ap_in_flight = None
        self.cur_block = None        # current flight plan block (ground NAV_STATUS)

    def connect(self, conf, ivy):
        self.conf = conf
        self.settings = PprzSettingsManager(conf.settings, conf.id, ivy)
        self.guided = GuidedMode(ivy)
        self.ivy = ivy
        self.blocks = fb.FlightPlanBlocks(conf)
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

    def _jump_to_block(self, candidates, what):
        if self.status == DroneStatus.UNKNOWN or self.blocks is None:
            logger.warning(f'{what}: drone not connected, ignored')
            return False
        block_id = self.blocks.find(candidates)
        if block_id is None:
            logger.warning(f"aircraft {self.conf.id}: no '{what}' block in "
                           f'flight plan (has: {self.blocks.names})')
            return False
        return self._send(lambda: fb.jump_to_block(self.ivy, self.conf.id, block_id))

    def start_motors(self): return self._jump_to_block(fb.MOTORS_CANDIDATES, 'start motors')
    def takeoff(self):      return self._jump_to_block(fb.TAKEOFF_CANDIDATES, 'takeoff')
    def land(self):         return self._jump_to_block(fb.LAND_CANDIDATES, 'land')

    def kill(self):
        """Cut the motors (kill_throttle): last resort, the drone falls."""
        if self.status == DroneStatus.UNKNOWN:
            return False
        try:
            self.settings['kill_throttle'] = 1
        except Exception as e:
            logger.warning(f'aircraft {self.conf.id}: kill failed ({e})')
            return False
        return True

FDStatus = Enum('FDStatus', [('STAGING', 1), ('GETTING_READY', 2), ('GUIDING', 3), ('FINISHED', 4)])      
class FlightDirector:
    def __init__(self, trajectories, ids):
        self.trajectories = trajectories
        self.pprz_connect = PprzConnect(notify=self.on_pprz_connect)
        self.pprz_connect.ivy.subscribe(self.on_pprz_flight_param, PprzMessage("telemetry", "ROTORCRAFT_FP"))
        self.pprz_connect.ivy.subscribe(self.on_pprz_external_pose, PprzMessage("datalink", "EXTERNAL_POSE"))
        self.pprz_connect.ivy.subscribe(self.on_pprz_status, PprzMessage("telemetry", "ROTORCRAFT_STATUS"))
        self.pprz_connect.ivy.subscribe(self.on_pprz_nav_status, PprzMessage("ground", "NAV_STATUS"))
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
        
    def on_pprz_external_pose(self, sender, msg):
        pos_enu = [msg[_c] for _c in ['enu_x', 'enu_y', 'enu_z']]
        quat = np.array([msg[_c] for _c in ['body_qi', 'body_qx', 'body_qy', 'body_qz']])
        rmat_enu2flu = p_al.rmat_of_quat(quat)
        T = np.eye(4); T[:3,3] = pos_enu; T[:3,:3] = rmat_enu2flu            
        try:
            ac = self.acs[int(sender)]
            #print("pose bine mis à jour")
        except KeyError: return # unknown
        ac.pose_source = 'external'
        ac.t_last_ext_pose = time.time()
        ac.set_pose(T)

    def run(self): # for now called from GUI thread, maybe use our own thread?
        if self.status == FDStatus.STAGING or self.status == FDStatus.GETTING_READY:
            elapsed = 0.
        else:
            elapsed = time.time() - self.t0
        if self.status == FDStatus.GUIDING:
            elapsed = elapsed % self.duree_du_show

        for idx_traj, id_ac in enumerate(self.ids): # compute reference pose
            traj = self.trajectories.get_trajectory(idx_traj)
            # each trajectory loops on its OWN period: the show wraps on the
            # longest one, and shorter trajectories (e.g. a 6.3s circle mixed
            # with a 20s course) used to teleport mid-lap at the global wrap
            t_traj = elapsed % traj.duration if traj.duration > 0 else elapsed
            Yref = traj.get(t_traj)
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
            # do NOT take control (Guided) here: in Guided the autopilot
            # ignores the flight plan, so the Start motors / Take off
            # block jumps would be dead. Drones stay in NAV until LAUNCH
            # SHOW arms Guided (on_guide_clicked).
        
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
        ac.t_last_status = time.time()
        ac.battery_v = float(msg['vsupply'])
        try:
            ac.rc_status = int(msg['rc_status'])
            ac.arming_status = int(msg['arming_status'])
            ac.ap_mode = int(msg['ap_mode'])
            ac.ap_motors_on = int(msg['ap_motors_on'])
            ac.ap_in_flight = int(msg['ap_in_flight'])
        except (KeyError, TypeError, ValueError):
            pass  # fields absent from this telemetry file: dots stay grey

    def on_pprz_nav_status(self, sender, msg):
        # ground-class message from the pprz server: the aircraft is a
        # field, not the Ivy sender
        try:
            ac = self.acs[int(msg['ac_id'])]
            ac.cur_block = int(msg['cur_block'])
        except (KeyError, TypeError, ValueError):
            return  # unknown aircraft or malformed message

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
        #super().__init__(args)
        self.setApplicationDisplayName("ClicknFly")
        self.setApplicationName("ClicknFly42")

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
        self.window.setWindowTitle("Click'n Fly - Spectator view")
        self.window.show()

        self.operator_view = OperatorWindow(self, self.model, self.fd)
        self.operator_view.show()

        #self.threadpool = QThreadPool()
        #self.worker = None

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
 
    def _flight_plan_step(self, label, action):
        """Send a flight plan jump to every drone of the scenario."""
        failed = [str(_id) for _id in self.fd.ids
                  if not action(self.fd.acs[_id])]
        if failed:
            self.operator_view.log_text(
                f'{label}: FAILED for drone(s) {", ".join(failed)} (see terminal log)')
        else:
            self.operator_view.log_text(f'{label} sent to {len(self.fd.ids)} drone(s)')

    def on_motors_clicked(self):
        self._flight_plan_step('Start motors', lambda d: d.start_motors())

    def on_takeoff_clicked(self):
        self._flight_plan_step('Takeoff', lambda d: d.takeoff())

    def on_land_all_clicked(self):
        """Emergency (or end-of-show) landing: stop guiding, hand every
        drone back to its flight plan on the land block."""
        self.operator_view.log_text('LAND ALL')
        self.is_guiding = False
        self.fd.status = FDStatus.FINISHED
        for ac_id in self.fd.ids:
            self.fd.acs[ac_id].release()  # back to NAV: the flight plan executes
        self._flight_plan_step('Land', lambda d: d.land())
        self.operator_view.button_guide.setEnabled(True)
        self.operator_view.button_stop.setEnabled(False)
        self.operator_view.set_preflight_enabled(True)

    def on_kill_clicked(self, ac_id):
        drone = self.fd.acs.get(ac_id) or self.fd.drone_pool.get(ac_id)
        if drone is None:
            self.operator_view.log_text(f'KILL {ac_id}: unknown drone')
            return
        if drone.kill():
            self.operator_view.log_text(f'KILL sent to drone {ac_id}')
        else:
            self.operator_view.log_text(f'KILL {ac_id}: FAILED (see terminal log)')

    def on_guide_clicked(self):
        #self.worker = Worker(self.model.get_trajectory(), self.traj_manager)
        #self.threadpool.start(self.worker)
        self.operator_view.log_text('Take off and trajectory following started')
        # arm Guided mode NOW, not at connect: before launch the drones
        # stay in NAV so the flight plan (start motors, takeoff blocks)
        # still executes. This is the single Guided entry point.
        results = [self.fd.acs[ac_id].take_control() for ac_id in self.fd.ids]
        if not all(results):
            self.operator_view.log_text(
                'WARNING: Ivy bus unavailable - is Paparazzi (server/simulator) running?')
        self.fd.status = FDStatus.STAGING
        self.is_guiding = True
        self.operator_view.button_guide.setEnabled(False)
        self.operator_view.button_stop.setEnabled(True)
        # a block jump would yank a drone out of the show: lock them out
        self.operator_view.set_preflight_enabled(False)

    def on_stop_clicked(self):
        self.operator_view.log_text("Show stopped: NAV Mode ")
        self.is_guiding = False
        self.fd.status = FDStatus.FINISHED
        for ac_id in self.fd.ids:
            self.fd.acs[ac_id].release()
        self.operator_view.button_guide.setEnabled(True)
        self.operator_view.button_stop.setEnabled(False)
        self.operator_view.set_preflight_enabled(True)

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
                    # no take_control here either: stay in NAV until launch
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
            # the drones panel doubles as the pre-flight checklist, so it
            # must live before takeoff, not only while guiding
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


scen1 = '''
ids: [4]
trajs: ["circle_with_intro1"]
'''
scen2 = '''
ids: [4,5]
trajs: ["circle_with_intro1", "circle_with_intro2"]
'''
scen3 = '''
ids: [4, 5, 6]
trajs: ["circle_with_intro1", "circle_with_intro2", "circle_with_intro3"]
'''
scen4 = '''
ids: [4, 5, 6, 7]
trajs: ["circle_with_intro1", "circle_with_intro2", "circle_with_intro3", "circle_with_intro4"]
'''
scen5 = '''
ids: [4,5]
trajs: ["smooth_back_and_forth1", "smooth_back_and_forth2"]
'''

scens = [scen1, scen2, scen3, scen4, scen5]

def parse_cli():
    parser = argparse.ArgumentParser(description='ClicknFly, flight director.')
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
        #print(chr(8)+chr(8),end="") # remove ^C from console... nope...
        logger.debug('Keyboard interrupt')
        cnf.on_quit()
        sys.exit()
    signal.signal(signal.SIGINT, _quit)
    cnf.exec()


if __name__ == '__main__':
    main()
