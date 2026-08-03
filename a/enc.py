# enc.py —— 编码器。capture() 刷缓冲区，get() 只读缓冲区，read() = 两者合一。
# 有 ticker 在跑时用 get()；没有 ticker 时必须用 read()，否则永远读到 0。
#
# 【关键】2026-08-03 实测：缓冲区里是**累计值**，不是本周期增量！
# 而且是 16 位有符号，32767 之后会翻到 -32768。
# 所以必须自己做差分 + 回绕处理，直接拿 get() 当速度是错的。
from smartcar import encoder

import cfg

# 2026-08-03 手转轮子实测确认：
#   物理左轮 = C2/C3（不取反），物理右轮 = C0/C1（要取反）。
#   向前转时两路计数都为正。
L = encoder('C2', 'C3', False)
R = encoder('C0', 'C1', True)

left  = 0        # 本周期左轮增量（已差分）
right = 0        # 本周期右轮增量（已差分）
speed = 0.0      # 一阶低通后的平均速度

_pl = 0          # 上一拍的累计值
_pr = 0


def _delta(now, prev):
    """16 位有符号回绕安全的差分。
    不用 if 判断，纯取模：把差值折回 -32768 ～ 32767 区间。"""
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
    """调参第 2 步：手推车向前，两个数都必须为正。

    这里必须用 read() 而不是 get()：没有 ticker 在跑时没人调 capture()。
    打印的是差分后的增量，不是累计值，停止时应该是 0。
    """
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