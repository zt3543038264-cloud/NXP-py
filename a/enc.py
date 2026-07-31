# enc.py —— 编码器。注意 get() 是“读取并清零”，一个周期只能调一次。
from smartcar import encoder

import cfg

L = encoder('C2', 'C3', False)
R = encoder('C0', 'C1', True)

left  = 0        # 本周期左轮计数
right = 0        # 本周期右轮计数
speed = 0.0      # 一阶低通后的平均速度


def reset():
    global left, right, speed
    L.get()          # 丢掉起步前累积的计数
    R.get()
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
    """调参第 2 步：手推车向前，两个数都必须为正。"""
    import time
    while True:
        print(L.get(), R.get())
        time.sleep_ms(200)