# enc.py —— 编码器。capture() 刷缓冲区，get() 只读缓冲区，read() = 两者合一。
# 有 ticker 在跑时用 get()；没有 ticker 时必须用 read()，否则永远读到 0。
from smartcar import encoder

import cfg

# 2026-08-01 实测修正：实际接在官方学习板的 1/2 号编码器接口。
# 物理左轮 = D15/D16（官方 ENCODER1），右轮 = D13/D14（官方 ENCODER2），且两路方向都要取反。
L = encoder('D15', 'D16', False)
R = encoder('D13', 'D14', True)

left  = 0        # 本周期左轮计数
right = 0        # 本周期右轮计数
speed = 0.0      # 一阶低通后的平均速度


def reset():
    global left, right, speed
    L.read()         # read() = capture + get，真正丢掉起步前累积的计数
    R.read()
    left = 0
    right = 0
    speed = 0.0


def update():
    """20 ms 调一次，且只能调一次。"""
    global left, right, speed
    left  = L.get()
    right = R.get()
    speed = 0.7 * speed + 0.3 * ((left + right) * 0.5)


def overspeed():
    lim = cfg.ENC_LIMIT
    return abs(left) > lim or abs(right) > lim


def test():
    """调参第 2 步：手推车向前，两个数都必须为正。

    这里必须用 read() 而不是 get()。没有 ticker 在跑时没人调 capture()，
    get() 只会一直返回缓冲区里的旧值 0。
    """
    import time
    while True:
        print(L.read(), R.read())
        time.sleep_ms(200)