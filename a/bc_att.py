# bc_att.py —— 姿态解算。输出的 angle 是真实度数，前倾为正。
import time
from math import atan2

import bc_cfg as cfg
import bc_hw as hw

angle   = 0.0      # 倾角 (deg)
rate    = 0.0      # 角速度 (deg/s)
gy_bias = 0.0      # 陀螺零偏 (LSB)


def calibrate(n=2000):
    """只标定陀螺仪零偏。车必须完全静止。约 2 秒。"""
    global gy_bias, angle
    s = 0
    for i in range(n):
        s += hw.imu.read()[4]
        time.sleep_ms(1)
    gy_bias = s / n
    d = hw.imu.read()
    angle = atan2(-d[0], d[2]) * cfg.RAD2DEG


def update():
    """5 ms 调一次。刷新 angle 和 rate。"""
    global angle, rate
    d = hw.imu.get()

    g = d[4] - gy_bias
    dead = cfg.GYRO_DEAD
    if dead and -dead < g < dead:
        g = 0.0
    rate = g / cfg.GYRO_LSB

    acc_angle = atan2(-d[0], d[2]) * cfg.RAD2DEG
    k = cfg.K_FILTER
    angle = k * (angle + rate * cfg.DT) + (1.0 - k) * acc_angle