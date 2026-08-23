# 读取双路编码器，计算周期增量、平均速度和超速状态。
from smartcar import encoder

import cfg

L = encoder('C2', 'C3', True)
R = encoder('C0', 'C1', False)

left = 0
right = 0
speed = 0.0
_pl = 0
_pr = 0

def _delta(now, prev):
    return ((now - prev + 32768) % 65536) - 32768

def reset():
    global left, right, speed, _pl, _pr
    _pl = L.read()
    _pr = R.read()
    left = 0
    right = 0
    speed = 0.0

def update():
    global left, right, speed, _pl, _pr
    cl = L.get()
    cr = R.get()
    left = _delta(cl, _pl)
    right = _delta(cr, _pr)
    _pl = cl
    _pr = cr
    speed = 0.7 * speed + 0.3 * ((left + right) * 0.5)

def overspeed():
    lim = cfg.ENC_LIMIT
    return abs(left) > lim or abs(right) > lim

def test():
    import time
    pl = L.read()
    pr = R.read()
    while True:
        time.sleep_ms(200)
        cl = L.read()
        cr = R.read()
        print(_delta(cl, pl), _delta(cr, pr))
        pl = cl
        pr = cr
