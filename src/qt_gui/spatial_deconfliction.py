#!/usr/bin/env python3
#
# Deconfliction by lambda-scheduling (path-velocity decomposition,
# Kant & Zucker 1986): for space-indexed trajectories Y(t) = G(lambda(t)),
# conflicts are resolved by reshaping the TIME LAWS only — a lower
# priority drone pauses ON ITS PATH just before the conflict zone until
# the other drone has cleared it. The geometry (the choreography) is
# strictly preserved, unlike start delays (drone parked at start) or
# reactive APF (deformed paths).
#
# Any trajectory can be scheduled: natively space-indexed ones are
# warped directly, and the others (Circle, Oval, composites...) are
# auto-converted through TimeGeometry — G(lambda) = Y(lambda*T) — which
# reproduces the original motion exactly under the nominal law t/T.
#
# v1 scope and honest limitations:
# - priority = scenario order (drone 0 never waits, drone 1 yields to 0...);
# - conflicts are resolved over the first show cycle; because holds
#   change durations, later loop cycles can drift into new phasings —
#   watch the live min inter-drone distance curve.
#
import logging
import numpy as np

import pat3.trajectory_1D as p_t1d
import pat3.vehicles.rotorcraft.multirotor_trajectory_dev as p_mt_dev

logger = logging.getLogger(__name__)


class HoldWarpedDyn:
    """Wrap a time->lambda law behind a time warp that freezes progress
    during a hold window: tau(t) runs at slope 1, flattens during the
    hold, then resumes. lambda(t) = orig(tau(t)), composed with the same
    4th-order chain rule SpaceIndexedTraj uses for G(lambda)."""

    def __init__(self, orig_dyn, t_hold, wait, eps=0.5):
        self.orig = orig_dyn
        self.duration = orig_dyn.duration + wait
        # piecewise-linear tau(t), corners smoothed like the project's
        # own dyn laws (SmoothedCompositeOne of AffOne segments)
        pts = []
        if t_hold > 1e-6:
            pts.append(((0., 0.), (t_hold, t_hold)))
        pts.append(((t_hold, t_hold), (t_hold + wait, t_hold)))
        pts.append(((t_hold + wait, t_hold), (self.duration, orig_dyn.duration)))
        segments = [p_t1d.AffOne(a, b) for a, b in pts]
        eps = min(eps, wait / 4., max(t_hold / 4., 1e-3))
        self.warp = p_t1d.SmoothedCompositeOne(segments, eps=eps)

    def get(self, t):
        w = self.warp.get(t)          # tau and its time derivatives
        g = self.orig.get(np.clip(w[0], 0., self.orig.duration))
        out = np.zeros(len(g))
        out[0] = g[0]
        out[1] = w[1]*g[1]
        out[2] = w[2]*g[1] + w[1]**2*g[2]
        out[3] = w[3]*g[1] + 3*w[1]*w[2]*g[2] + w[1]**3*g[3]
        out[4] = w[4]*g[1] + (3*w[2]**2 + 4*w[1]*w[3])*g[2] \
                 + 6*w[1]**2*w[2]*g[3] + w[1]**4*g[4]
        return out


class TimeGeometry:
    """Any trajectory reinterpreted as pure geometry: G(l) = Y(l*T).
    Time-derivatives become lambda-derivatives (one factor T per order),
    so composing with a time law through SpaceIndexedTraj reproduces the
    exact original motion under the nominal law l(t) = t/T — and makes
    the trajectory schedulable like a native space-indexed one."""
    _ylen, _nder = 4, 5

    def __init__(self, traj):
        self.traj = traj
        self.T = float(traj.duration)

    def get(self, l):
        Y = np.asarray(self.traj.get(float(np.clip(l, 0., 1.)) * self.T))
        G = np.empty_like(Y)
        f = 1.
        for d in range(Y.shape[1]):
            G[:, d] = Y[:, d] * f
            f *= self.T
        return G


def make_space_indexed(traj):
    """Wrap any trajectory into an equivalent SpaceIndexedTraj."""
    geom = TimeGeometry(traj)
    dyn = p_t1d.AffOne((0., 0.), (geom.T, 1.))
    si = p_mt_dev.SpaceIndexedTraj(geom, dyn)
    si.name = getattr(traj, 'name', 'converted')
    si.desc = (getattr(traj, 'desc', '') + ' [schedulable]').strip()
    return si


def _space_indexed_of(traj):
    """Return (inner SpaceIndexedTraj, outer object) or (None, traj).
    Handles both direct subclasses (queue leu leu, figures of height)
    and wrappers holding one in .traj (race track, slalom)."""
    if isinstance(traj, p_mt_dev.SpaceIndexedTraj):
        return traj, traj
    inner = getattr(traj, 'traj', None)
    if isinstance(inner, p_mt_dev.SpaceIndexedTraj):
        return inner, traj
    return None, traj


def insert_hold(traj, t_hold, wait):
    """Pause the drone on its path at t_hold for `wait` seconds.
    Returns False if the trajectory is not space-indexed."""
    si, outer = _space_indexed_of(traj)
    if si is None:
        return False
    warped = HoldWarpedDyn(si._dyn, t_hold, wait)
    si.set_dyn(warped)
    si.duration = warped.duration          # set_dyn does not refresh it
    if outer is not si:
        outer.duration = warped.duration   # wrappers keep their own copy
    return True


def _positions_at(trajs, t):
    """Per-trajectory looping, same convention as the FlightDirector."""
    out = []
    for traj in trajs:
        tt = t % traj.duration if traj.duration > 0 else t
        out.append(traj.get(tt)[:3, 0])
    return out


def _first_conflict(trajs, safety_distance, dt):
    """Earliest conflict over one cycle of the longest trajectory:
    returns (i, j, t_start, t_end) with i < j, or None."""
    T = max(tr.duration for tr in trajs)
    n = len(trajs)
    active = None
    for t in np.arange(0., T, dt):
        pos = _positions_at(trajs, t)
        hit = None
        for i in range(n):
            for j in range(i + 1, n):
                if np.linalg.norm(pos[i] - pos[j]) < safety_distance:
                    hit = (i, j)
                    break
            if hit: break
        if active is None and hit is not None:
            active = (hit[0], hit[1], t)
        elif active is not None and (hit is None or hit[:2] != active[:2]):
            i, j, t1 = active
            return i, j, t1, t
    if active is not None:
        i, j, t1 = active
        return i, j, t1, T
    return None


def resolve_conflicts_spatial(model, safety_distance=1.0, margin_t=1.0,
                              dt=0.1, max_iter=10):
    """Iteratively schedule away every conflict of the scenario.
    Returns (ok, report_lines)."""
    report = []
    for _ in range(max_iter):
        trajs = [model.get_trajectory(i) for i in range(model.trajectory_nb())]
        c = _first_conflict(trajs, safety_distance, dt)
        if c is None:
            return True, report
        i, j, t1, t2 = c
        t_hold = max(0., t1 - margin_t)
        wait = (t2 - t1) + 2. * margin_t
        traj_j = trajs[j]
        if _space_indexed_of(traj_j)[0] is None:
            # not natively space-indexed: swap in the equivalent
            # schedulable version (identical motion, indexable timing)
            traj_j = make_space_indexed(traj_j)
            model.set_trajectory(traj_j, j)
            report.append(f'drone {j+1}: converted to space-indexed for scheduling')
        if not insert_hold(traj_j, t_hold, wait):
            report.append(f'drone {j+1}: could not warp its time law')
            return False, report
        report.append(f'drone {j+1} pauses {wait:.1f}s on its path at '
                      f't={t_hold:.1f}s (conflict with drone {i+1} '
                      f'at {t1:.1f}-{t2:.1f}s)')
        logger.info(report[-1])
    report.append(f'still conflicting after {max_iter} holds, giving up')
    return False, report
