#import traj_factory # not needed?


class Scenario:
    pass

class Scenario1:
    desc  = 'single circle with intro'
    ids= [112]
    trajs= ["circle_with_intro1"]

class Scenario2:
    desc  = 'two circles with intro'
    ids= [112, 113]
    trajs= ["circle_with_intro1", "circle_with_intro2"]

class Scenario3:
    desc  = 'three circles with intro'
    ids= [112, 113, 114]
    trajs= ["circle_with_intro1", "circle_with_intro2", "circle_with_intro3"]

class Scenario4:
    desc  = 'two back-and-forth'
    ids= [112, 113]
    trajs= ["smooth_back_and_forth1", "smooth_back_and_forth2"]

class Scenario5:
    desc  = 'gate race, solo'
    ids = [112]
    trajs = ["space indexed gate race1"]
    arena = "data/arena_3.yaml"

class Scenario6:
    desc  = 'scara race, solo'
    ids = [112]
    trajs = ["scara race"]
    arena = "data/arena_112.yaml"

class Scenario7:
    desc  = 'circle then back-and-forth'
    ids= [112]
    trajs= ["cercle_back_and_forth"]

class Scenario8:   # deux figure-of-eight a la meme hauteur, conflit au centre
    # order matters: each drone flies the eight that STARTS on the same side
    # as its standby point (112 -> standby [-2,-2] left, left-start eight;
    # 113 -> standby [2,-2] right, right-start eight), so the undeconflicted
    # standby<->start transits stay on their own side and don't cross. The two
    # eights conflict at the centre during the show (same height z=2).
    desc  = 'two figure-of-eight'
    ids   = [112, 113]
    trajs = ['space indexed figure of height3 flat', 'space indexed figure of height']

class Scenario9:
    desc  = 'two concentric safe circles'
    ids = [112, 113]
    trajs = ["cercle safe 1", "cercle safe 2"]

class Scenario10:
    desc  = 'three concentric safe circles'
    ids = [112, 113, 114]
    trajs = ["cercle safe 1", "cercle safe 2", "cercle safe 3"]

class Scenario11:   # rotating triangle
    desc  = 'rotating triangle'
    ids   = [112, 113, 114]
    trajs = ['show rosette a', 'show rosette b', 'show rosette c']

class Scenario12:   # swirling tower, 3 drones
    desc  = 'swirling tower, 3 drones'
    ids   = [112, 113, 114]
    trajs = ['show tornado inner', 'show tornado mid', 'show tornado outer']

class Scenario13:   # swirling tower, 2 drones (inner + outer, separated in r and z)
    desc  = 'swirling tower, 2 drones'
    ids   = [112, 113]
    trajs = ['show tornado inner', 'show tornado outer']

class Scenario14:   # counter-rotating rings
    desc  = 'counter-rotating rings'
    ids   = [112, 113]
    trajs = ['show twin ring low', 'show twin ring high']

class Scenario15:  # pulsing ring
    desc  = 'pulsing ring'
    ids   = [112, 113, 114]
    trajs = ['show pulse a', 'show pulse b', 'show pulse c']

class Scenario16:  # stacked ovals
    desc  = 'stacked ovals'
    ids   = [112, 113]
    trajs = ['show oval low', 'show oval high']

class Scenario17:  # lissajous solo
    desc  = 'lissajous solo'
    ids   = [112]
    trajs = ['show lissajous']

class Scenario18:  # convergence a 3
    desc  = 'three-way convergence'
    ids   = [112, 113, 114]
    trajs = ['conflit tri a', 'conflit tri b', 'conflit tri c']

class Scenario19:   # spirale montante a 3 drones
    desc  = 'ascending spiral, 3 drones'
    ids   = [112, 113, 114]
    trajs = ['spirale a', 'spirale b', 'spirale c']

class Scenario20:   # spirale a 2 drones
    desc  = 'spiral, 2 drones'
    ids   = [112, 113]
    trajs = ['spirale a', 'spirale c']

class Scenario21:   # vraie spirale montante a 3 drones
    desc  = 'true ascending spiral, 3 drones'
    ids   = [112, 113, 114]
    trajs = ['spirale montante a', 'spirale montante b', 'spirale montante c']

class Scenario22:   # vraie spirale montante a 2 drones (memes helices, dephasees)
    desc  = 'true ascending spiral, 2 drones'
    ids   = [112, 113]
    trajs = ['spirale montante a', 'spirale montante c']

class Scenario23:   # fleur qui s'ouvre/se ferme, 3 drones
    desc  = 'blooming flower, 3 drones'
    ids   = [112, 113, 114]
    trajs = ['flower a', 'flower b', 'flower c']

class Scenario24:   # double helice / ADN, 2 drones
    desc  = 'double helix (DNA), 2 drones'
    ids   = [112, 113]
    trajs = ['dna strand a', 'dna strand b']

class Scenario25:   # cascade en escalier, 3 drones
    desc  = 'cascade staircase, 3 drones'
    ids   = [112, 113, 114]
    trajs = ['cascade low', 'cascade mid', 'cascade high']

class Scenario26:   # spirographe / rosace epicyclique, solo
    desc  = 'spirograph rosette, solo'
    ids   = [112]
    trajs = ['show spirograph']

class Scenario27:   # noeud torique 3D, solo
    desc  = '3D torus knot, solo'
    ids   = [112]
    trajs = ['show knot']

class Scenario28:   # tour de rosaces etagees, 2 drones (safe: separees en hauteur)
    desc  = 'spirograph tower, 2 drones'
    ids   = [112, 113]
    trajs = ['show spirograph low', 'show spirograph high']

class Scenario29:   # fontaine / eclosion, 3 drones (safe: 120 deg d'azimut)
    desc  = 'fountain bloom, 3 drones'
    ids   = [112, 113, 114]
    trajs = ['fountain a', 'fountain b', 'fountain c']

class Scenario30:   # formation morphing ligne<->triangle, 3 drones
    desc  = 'morphing formation (line/triangle), 3 drones'
    ids   = [112, 113, 114]
    trajs = ['morph a', 'morph b', 'morph c']


scenarios = [
    Scenario1,
    Scenario2,
    Scenario3,
    Scenario4,
    Scenario5,
    Scenario6,
    Scenario7,
    Scenario8,
    Scenario9,
    Scenario10,
    Scenario11,
    Scenario12,
    Scenario13,
    Scenario14,
    Scenario15,
    Scenario16,
    Scenario17,
    Scenario18,
    Scenario19,
    Scenario20,
    Scenario21,
    Scenario22,
    Scenario23,
    Scenario24,
    Scenario25,
    Scenario26,
    Scenario27,
    Scenario28,
    Scenario29,
    Scenario30,
    ]


# --- conflict grouping (operator scenario picker) -----------------------
# Split the predefined scenarios into two groups for the picker: those
# designed conflict-free (solo, concentric, height/radius-separated) and
# those with inter-drone conflicts (crossing or converging paths -- the
# deconfliction testbeds). To move a scenario to the other group, just move
# its class name between the two lists below; anything left out defaults to
# no-conflict.
_WITH_CONFLICT = [
    Scenario4,    # two back-and-forth (head-on)
    Scenario8,    # two figure-of-eight, same height (cross at centre)
    Scenario18,   # three-way convergence
]

for _c in scenarios:
    _c.conflict = _c in _WITH_CONFLICT


# --- default drone ids -------------------------------------------------
# The scenarios are authored with ids 112, 113, 114 (drone slot 0, 1, 2).
# Map them onto the actual lab fleet, by slot, so every scenario defaults to
# the real drones. Change FLEET_IDS to renumber every scenario at once (the
# operator can still remap per-scenario in the picker).
FLEET_IDS = [110, 112, 111]
_ID_REMAP = {112: FLEET_IDS[0], 113: FLEET_IDS[1], 114: FLEET_IDS[2]}
for _c in scenarios:
    _c.ids = [_ID_REMAP.get(_id, _id) for _id in _c.ids]
