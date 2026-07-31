# tick.py —— 定时器。唯一需要同时认识多个外设的硬件模块。
from smartcar import ticker

import imu
import key
import enc

flag5  = False
flag20 = False


def _cb5(t):
    global flag5
    flag5 = True


def _cb20(t):
    global flag20
    flag20 = True


pit0 = ticker(0)
pit0.capture_list(imu.dev, key.dev)
pit0.callback(_cb5)

pit2 = ticker(2)
pit2.capture_list(enc.L, enc.R)
pit2.callback(_cb20)


def start():
    global flag5, flag20
    flag5 = False
    flag20 = False
    pit0.start(5)
    pit2.start(20)


def stop():
    pit0.stop()
    pit2.stop()