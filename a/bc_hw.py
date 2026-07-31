# bc_hw.py —— 所有硬件对象。import 时完成初始化，只会执行一次。
from machine import UART
from smartcar import ticker, encoder
from seekfree import MOTOR_CONTROLLER, IMU660RX, KEY_HANDLER

import bc_cfg as cfg

imu     = IMU660RX(1)
enc_l   = encoder('C2', 'C3', False)
enc_r   = encoder('C0', 'C1', True)
key     = KEY_HANDLER(5)
motor_L = MOTOR_CONTROLLER(MOTOR_CONTROLLER.PWM_D4_DIR_D5, 5000,
                           duty=0, invert=False)
motor_R = MOTOR_CONTROLLER(MOTOR_CONTROLLER.PWM_D6_DIR_D7, 5000,
                           duty=0, invert=False)

# 蓝牙/无线透传，LPUART3 = C6/C7。波特率必须和模块配置一致。
uart = UART(2)
uart.init(115200, bits=8, parity=None, stop=1)

# ---- 定时器标志。回调只置标志，一行运算都不做。 ----
flag5  = False
flag20 = False


def _cb5(t):
    global flag5
    flag5 = True


def _cb20(t):
    global flag20
    flag20 = True


pit1 = ticker(0)
pit1.capture_list(imu, key)
pit1.callback(_cb5)

pit3 = ticker(2)
pit3.capture_list(enc_l, enc_r)
pit3.callback(_cb20)


def start_tickers():
    pit1.start(5)
    pit3.start(20)


def stop_tickers():
    pit1.stop()
    pit3.stop()


def clamp(v, lo, hi):
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


def stop_motor():
    motor_L.duty(0)
    motor_R.duty(0)


def set_motor(l, r):
    lim = cfg.DUTY_LIMIT
    sign = cfg.MOTOR_SIGN
    motor_L.duty(int(clamp(l, -lim, lim)) * sign)
    motor_R.duty(int(clamp(r, -lim, lim)) * sign)