# 驱动左右电机，处理极性、死区补偿和输出限幅。
from seekfree import MOTOR_CONTROLLER

import cfg

L = MOTOR_CONTROLLER(MOTOR_CONTROLLER.PWM_D6_DIR_D7, 5000,
                     duty=0, invert=False)
R = MOTOR_CONTROLLER(MOTOR_CONTROLLER.PWM_D4_DIR_D5, 5000,
                     duty=0, invert=True)

def stop():
    L.duty(0)
    R.duty(0)

def _kick(v, dead):
    """死区补偿。"""
    if dead <= 0 or v == 0:
        return v
    if v > 0:
        return v + dead
    return v - dead

def drive(l, r):
    """限幅 + 整体极性。"""
    lim = cfg.DUTY_LIMIT
    s = cfg.MOTOR_SIGN
    d = cfg.DEAD_DUTY
    L.duty(int(cfg.clamp(_kick(l, d), -lim, lim)) * s)
    R.duty(int(cfg.clamp(_kick(r, d), -lim, lim)) * s)

def test(duty=800, ms=1000):
    """调参第 1 步：轮子离地，左右轮各转一秒，看方向。"""
    import time
    try:
        print('L (D6/D7) turning now')
        L.duty(duty)
        time.sleep_ms(ms)
        L.duty(0)
        time.sleep_ms(500)
        print('R (D4/D5) turning now')
        R.duty(duty)
        time.sleep_ms(ms)
        R.duty(0)
    finally:
        stop()      # Ctrl+C 或任何异常都保证归零