from smartcar import ticker
import imu
import key
import enc
import ccd

VER = '0812a'
flag5 = False
flag10 = False
flag20 = False

def _cb5(t):
    global flag5
    flag5 = True

def _cb10(t):
    global flag10
    flag10 = True

def _cb20(t):
    global flag20
    flag20 = True

pit0 = ticker(0)
pit0.capture_list(imu.dev)
pit0.callback(_cb5)
pit1 = ticker(1)
pit1.capture_list(ccd.dev)
pit1.callback(_cb10)
pit2 = ticker(2)
pit2.capture_list(enc.L, enc.R)
pit2.callback(_cb20)

def start():
    global flag5, flag10, flag20
    flag5 = False
    flag10 = False
    flag20 = False
    pit0.start(5)
    pit1.start(10)
    pit2.start(20)

def stop():
    pit0.stop()
    pit1.stop()
    pit2.stop()
