# motor.py —— 电机。唯一一处把控制量变成实际转动的地方。
from seekfree import MOTOR_CONTROLLER

import cfg

L = MOTOR_CONTROLLER(MOTOR_CONTROLLER.PWM_D4_DIR_D5, 5000,
                     duty=0, invert=False)
R = MOTOR_CONTROLLER(MOTOR_CONTROLLER.PWM_D6_DIR_D7, 5000,
                     duty=0, invert=False)


def stop():
    L.duty(0)
    R.duty(0)


def drive(l, r):
    """限幅 + 整体极性。故意不叫 set()，避免遮蔽内置函数。"""
    lim = cfg.DUTY_LIMIT
    s = cfg.MOTOR_SIGN
    L.duty(int(cfg.clamp(l, -lim, lim)) * s)
    R.duty(int(cfg.clamp(r, -lim, lim)) * s)


def test(duty=2000, ms=1000):
    """调参第 1 步：轮子离地，左右轮各转一秒，看方向。"""
    import time
    print('LEFT  forward?')
    L.duty(duty)
    time.sleep_ms(ms)
    L.duty(0)
    time.sleep_ms(500)
    print('RIGHT forward?')
    R.duty(duty)
    time.sleep_ms(ms)
    R.duty(0)