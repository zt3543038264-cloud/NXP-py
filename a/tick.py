# 配置 5 ms 与 20 ms 定时采集和任务标志。
from smartcar import ticker

import imu
import key
import enc
import ccd

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
pit2.capture_list(enc.L, enc.R, ccd.dev)
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