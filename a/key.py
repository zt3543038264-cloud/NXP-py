# key.py —— 按键。参数是扫描周期 (ms)，必须等于 ticker 周期。
from seekfree import KEY_HANDLER

dev = KEY_HANDLER(5)

# 已实测 2026-07-31：KEY1~KEY4 对应下标 0~3，按下为 1，自动回 0。
# get() 返回 6 个元素，后两个恒为 0，不用管。
START = 0        # KEY1
STOP  = 1        # KEY2


def pressed(idx):
    return dev.get()[idx]


def clear(idx=None):
    if idx is None:
        dev.clear()
    else:
        dev.clear(idx)


def test():
    """调参第 0 步：四个键逐个按，记下下标、按下时的值、松手后是否自动清零。"""
    import time
    while True:
        dev.capture()
        print(dev.get())
        time.sleep_ms(200)