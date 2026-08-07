# 读取板载按键并提供按键测试。
from seekfree import KEY_HANDLER

dev = KEY_HANDLER(5)

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