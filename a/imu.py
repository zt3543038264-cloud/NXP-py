# 读取 IMU，计算俯仰角、俯仰角速度和偏航角速度。
import time
from math import atan2
from seekfree import IMU660RX

import cfg

dev = IMU660RX(1)
angle = 0.0
rate = 0.0
yaw_rate = 0.0
gy_bias = 0.0
gz_bias = 0.0

def calibrate(n=2000):
    global gy_bias, gz_bias, angle
    dev.read()
    sy = 0
    sz = 0
    for i in range(n):
        d = dev.read()
        sy += d[4]
        sz += d[5]
        time.sleep_ms(1)
    gy_bias = sy / n
    gz_bias = sz / n
    d = dev.read()
    angle = atan2(-d[0], d[2]) * cfg.RAD2DEG

def update():
    global angle, rate, yaw_rate
    d = dev.get()
    dead = cfg.GYRO_DEAD
    g = d[4] - gy_bias
    if dead and -dead < g < dead:
        g = 0.0
    rate = g / cfg.GYRO_LSB
    z = d[5] - gz_bias
    if dead and -dead < z < dead:
        z = 0.0
    yaw_rate = z / cfg.GYRO_LSB
    acc_angle = atan2(-d[0], d[2]) * cfg.RAD2DEG
    k = cfg.K_FILTER
    angle = k * (angle + rate * cfg.DT) + (1.0 - k) * acc_angle

def fallen():
    return abs(angle - cfg.MID_ANGLE) > cfg.ANGLE_LIMIT
