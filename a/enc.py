# 读取双路编码器，计算周期增量、平均速度和超速状态。
from smartcar import encoder

import cfg

L = encoder('C2', 'C3', False)
R = encoder('C0', 'C1', True)

left  = 0        # 本周期左轮增量（已差分）
right = 0        # 本周期右轮增量（已差分）
speed = 0.0      # 一阶低通后的平均速度

_pl = 0          # 上一拍的累计值
_pr = 0

def _delta(now, prev):
    """16 位有符号回绕安全的差分。"""
    return ((now - prev + 32768) % 65536) - 32768

def reset():
    global left, right, speed, _pl, _pr
    _pl = L.read()   # 不是“清零”，是把当前累计值记下来当基准
    _pr = R.read()
    left = 0
    right = 0
    speed = 0.0

def update():
    """20 ms 调一次，且只能调一次。"""
    global left, right, speed, _pl, _pr
    cl = L.get()
    cr = R.get()
    left  = _delta(cl, _pl)
    right = _delta(cr, _pr)
    _pl = cl
    _pr = cr
    speed = 0.7 * speed + 0.3 * ((left + right) * 0.5)

def overspeed():
    lim = cfg.ENC_LIMIT
    return abs(left) > lim or abs(right) > lim

def test():
    """调参第 2 步：手推车向前，两个数都必须为正。"""
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