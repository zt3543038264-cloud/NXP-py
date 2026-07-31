# bt.py —— 蓝牙/无线串口文本协议。没接模块时也能安全跑，写出去没人收而已。
from machine import UART

import cfg

# LPUART3 = C6/C7。波特率必须和模块实际配置一致。
uart = UART(2)
uart.init(115200, bits=8, parity=None, stop=1)

_buf = ''


def say(text):
    uart.write(text)


def report(angle, target_angle, speed, pwm):
    """遥测。数据从外面传进来，避免反过来 import balance 造成循环引用。"""
    uart.write('%.2f %.2f %.1f %.0f\\n' % (angle, target_angle, speed, pwm))


def poll(allow_save=False):
    """非阻塞。返回 'stop' 表示远程停车，否则 None。

    协议：一行一条
        BAL_KP=260   改参数（只改内存，立即生效）
        ?            回传全部参数
        S            存盘（仅 idle 时允许）
        X            远程停车
    """
    global _buf
    n = uart.any()
    if n:
        try:
            _buf += uart.read(n).decode()
        except Exception:
            _buf = ''
            return None
        if len(_buf) > 200:        # 收到乱码时防止无限增长
            _buf = ''
            return None
    if '\\n' not in _buf:
        return None

    line, _buf = _buf.split('\\n', 1)
    line = line.strip()
    if not line:
        return None

    if line == 'X':
        return 'stop'

    if line == '?':
        for k in sorted(cfg.P):
            uart.write('%s=%s\\n' % (k, cfg.P[k]))
        return None

    if line == 'S':
        if allow_save:
            cfg.save_params()
            uart.write('saved\\n')
        else:
            uart.write('busy: stop the car first\\n')
        return None

    if '=' in line:
        k, v = line.split('=', 1)
        k = k.strip()
        try:
            ok = cfg.setp(k, float(v), save=False)
        except ValueError:
            ok = False
        if ok:
            uart.write('ok %s=%s\\n' % (k, cfg.P[k]))
        else:
            uart.write('reject %s\\n' % line)
    return None