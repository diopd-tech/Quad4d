import numpy as np


def repulsive_acc(p_self, v_self, others_pv, d0=1.5, d_min=0.4, k_max=6.0, tau=1.0):    
    
    acc = np.zeros(3)
    for p_o, v_o in others_pv:
        r0 = np.asarray(p_self) - np.asarray(p_o)        # relative position
        v  = np.asarray(v_self) - np.asarray(v_o)        # relative velocity
        vv = float(v @ v)
        t_star = 0.0 if vv < 1e-9 else np.clip(-(r0 @ v) / vv, 0.0, tau)
        r_pred = r0 + v * t_star                         # separation at closest approach
        d = np.linalg.norm(r_pred)
        if d >= d0:
            continue
        # direction: predicted separation; fall back to current if degenerate (head-on)
        n = r_pred / d if d > 1e-3 else r0 / max(np.linalg.norm(r0), 1e-6)
        d_eff = max(d, 1e-3)
        x = np.clip((d0 - d_eff) / (d0 - d_min), 0.0, 1.0)
        s = x * x * x * (x * (6.0 * x - 15.0) + 10.0)
        acc += k_max * s * n
    return acc


class ReactiveAvoidance:

    def __init__(self, d0=1.2, d_min=0.4, k_max=4.0, zeta=2.0 , tau=1.0,
                 mode='deform', z_weight=1.0, bounds=None, dp_max=None):
        self.d0, self.d_min, self.k_max = d0, d_min, k_max
        self.zeta = zeta
        self.tau = tau
        self.mode = mode
        self.z_weight = z_weight  # <1 to soften vertical pushes (height already separated)
        self.bounds = bounds
        self.dp_max = dp_max      # hard cap (m) on the deformation amplitude:
                                  # the integrator has momentum (dv keeps dp
                                  # growing after the threat has passed), this
                                  # bounds how far a reference can coast away
        self.dp = {}
        self.dv = {}
        #self.omega = omega


    def reset(self):
        self.dp.clear()
        self.dv.clear()

    def apply(self, ids, Yrefs, positions, dt):
        """Mutate Yrefs in place.

        ids       : ordered list of aircraft ids
        Yrefs     : dict id -> Yref (4,5) ENU  (MODIFIED IN PLACE)
        positions : dict id -> (3,) measured ENU position (from EXTERNAL_POSE)
        dt        : seconds since last call
        """
        if dt <= 0.0:
            return
        vel = {i: Yrefs[i][:3, 1].copy() for i in ids}
        for i in ids:
            others_pv = [(positions[j], vel[j]) for j in ids
                        if j != i and j in positions]
            if i in positions and others_pv:
                da_rep = repulsive_acc(positions[i], vel[i], others_pv,
                                    self.d0, self.d_min, self.k_max, self.tau)
                da_rep[2] *= self.z_weight
            else:
                da_rep = np.zeros(3)

            dp = self.dp.get(i, np.zeros(3))
            dv = self.dv.get(i, np.zeros(3))
            da = da_rep - 2.0 * self.zeta * dv - (self.zeta ** 2) * dp
            #da = da_rep - 2.0*self.zeta*self.omega*dv - (self.omega**2)*dp   # >>> MODIF : ζ et ω indépendants
            dv = dv + da * dt
            dp = dp + dv * dt

            # cap the deformation amplitude: kill the outward velocity when
            # saturated so the offset doesn't fight the cap
            if self.dp_max is not None:
                n = np.linalg.norm(dp)
                if n > self.dp_max:
                    dp *= self.dp_max / n
                    outward = float(dv @ dp) / max(float(dp @ dp), 1e-9)
                    if outward > 0.:
                        dv -= outward * dp   # remove the component pushing past the cap

            Yrefs[i][:3, 0] += dp
            Yrefs[i][:3, 1] += dv
            Yrefs[i][:3, 2] += da

            # >>> À VÉRIFIER : keep the deformed reference inside the arena.
            if self.bounds is not None:
                p_cmd = Yrefs[i][:3, 0]
                for k, (lo, hi) in enumerate(self.bounds):
                    if p_cmd[k] < lo or p_cmd[k] > hi:
                        clamped = np.clip(p_cmd[k], lo, hi)
                        dp[k] += clamped - p_cmd[k]   # absorb the clamp into the offset
                        p_cmd[k] = clamped
                        dv[k] = 0.0

            self.dp[i], self.dv[i] = dp, dv