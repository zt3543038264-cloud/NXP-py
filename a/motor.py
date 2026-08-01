# motor.py —— 电机。唯一一处把控制量变成实际转动的地方。
from seekfree import MOTOR_CONTROLLER

import cfg

# 实际接线：C30/C31 和 C28/C29。哪组是左轮还没验证，
# 跑 motor.test() 时看“LEFT”那一秒到底是哪个轮子在转，反了就把下面两行对调。
L = MOTOR_CONTROLLER(MOTOR_CONTROLLER.PWM_C30_DIR_C31, 5000,
                     duty=0, invert=False)
R = MOTOR_CONTROLLER(MOTOR_CONTROLLER.PWM_C28_DIR_C29, 5000,
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


def test(duty=800, ms=1000):
    """调参第 1 步：轮子离地，左右轮各转一秒，看方向。

    800 是满量程（±10000）的 8%。不转先往上加，不要直接往下降——
    低于死区时电机只响不转，堵转电流会把驱动烤热。
    """
    import time
    try:
        print('L (C30/C31) turning now')
        L.duty(duty)
        time.sleep_ms(ms)
        L.duty(0)
        time.sleep_ms(500)
        print('R (C28/C29) turning now')
        R.duty(duty)
        time.sleep_ms(ms)
        R.duty(0)
    finally:
        stop()      # Ctrl+C 或任何异常都保证归零