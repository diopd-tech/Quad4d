#import traj_factory # not needed?


class Scenario:
    pass

class Scenario1:
    ids= [112]
    trajs= ["circle_with_intro1"]

class Scenario2:
    ids= [112, 113]
    trajs= ["circle_with_intro1", "circle_with_intro2"]

class Scenario3:
    ids= [112, 113, 114]
    trajs= ["circle_with_intro1", "circle_with_intro2", "circle_with_intro3"]

class Scenario4:
    ids= [112, 113, 114, 115]
    trajs= ["circle_with_intro1", "circle_with_intro2", "circle_with_intro3", "circle_with_intro112"]

class Scenario5:
    ids= [112, 113]
    trajs= ["smooth_back_and_forth1", "smooth_back_and_forth2"]

class Scenario6:
    ids = [112]
    trajs = ["space indexed gate race1"]
    arena = "data/arena_3.yaml"

class Scenario7:
    ids = [112]
    trajs = ["scara race"]
    arena = "data/arena_112.yaml"

class Scenario8:
    ids= [112]
    trajs= ["cercle_back_and_forth"]

class Scenario9:
    ids= [112, 113, 114]
    trajs= ["smooth_back_and_forth1", "space indexed gate race1", "circle_with_intro1"]

class Scenario10:
    ids= [112, 113, 114]
    trajs= ["space indexed oval", "space indexed figure of height2", "space indexed gate race1"]


class Scenario11:
    ids= [112, 113, 114]
    trajs= ["queue leu leu 1", "queue leu leu 2", "queue leu leu 3"]

class Scenario12:
    ids= [112, 113]
    trajs= ["space indexed race track 1", "space indexed slalon"]

class Scenario13:
    ids= [112, 113]
    trajs= ["queue leu leu 1", "queue leu leu 2"]

class Scenario14:
    ids= [112, 113]
    trajs= ["space indexed figure of height", "space indexed figure of height3"]

class Scenario15: 
    ids = [112, 113]
    trajs = ["cercle safe 1", "cercle safe 2"]

class Scenario16: 
    ids = [112, 113, 114]
    trajs = ["cercle safe 1", "cercle safe 2", "cercle safe 3"]



class Scenario17:   # rotating triangle
    desc  = 'rotating triangle'
    ids   = [112, 113, 114]
    trajs = ['show rosette a', 'show rosette b', 'show rosette c']

class Scenario18:   # swirling tower
    desc  = 'swirling tower'
    ids   = [112, 113, 114]
    trajs = ['show tornado inner', 'show tornado mid', 'show tornado outer']

class Scenario19:   # counter-rotating rings
    desc  = 'counter-rotating rings'
    ids   = [112, 113]
    trajs = ['show twin ring low', 'show twin ring high']

class Scenario20:  # pulsing ring
    desc  = 'pulsing ring'
    ids   = [112, 113, 114]
    trajs = ['show pulse a', 'show pulse b', 'show pulse c']

class Scenario21:  # stacked ovals
    desc  = 'stacked ovals'
    ids   = [112, 113]
    trajs = ['show oval low', 'show oval high']

class Scenario22:  # lissajous solo
    desc  = 'lissajous solo'
    ids   = [112]
    trajs = ['show lissajous']

class Scenario23:  # star solo
    desc  = 'star solo'
    ids   = [112]
    trajs = ['show star']


class Scenario24:  # convergence a 3
    desc  = 'convergence a 3'
    ids   = [112, 113, 114]
    trajs = ['conflit tri a', 'conflit tri b', 'conflit tri c']


class Scenario25:   # spirale montante a 3 drones
    desc  = 'spirale montante a 3 drones'
    ids   = [112, 113, 114]
    trajs = ['spirale a', 'spirale b', 'spirale c']

class Scenario26:   # spirale a 2 drones
    desc  = 'spirale a 2 drones'
    ids   = [112, 113]
    trajs = ['spirale a', 'spirale c']

class Scenario27:   # vraie spirale montante a 3 drones
    desc  = 'vraie spirale montante a 3 drones'
    ids   = [112, 113, 114]
    trajs = ['spirale montante a', 'spirale montante b', 'spirale montante c']


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
    Scenario27
    ]

