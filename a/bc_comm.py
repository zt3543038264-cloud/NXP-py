# bc_comm.py —— 蓝牙/无线串口文本协议。
import bc_cfg as cfg
import bc_hw as hw

_buf = ''


def poll(allow_save=False):
    """非阻塞。返回 'stop' 表示远程停车，否则 None。

    协议：一行一条
        BAL_KP=260   改参数（只改内存，立即生效）
        ?            回传全部参数
        S            存盘（仅 idle 时允许）
        X            远程停车
    """
    global _buf
    n = hw.uart.any()
    if n:
        try:
            _buf += hw.uart.read(n).decode()
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
            hw.uart.write('%s=%s\\n' % (k, cfg.P[k]))
        return None

    if line == 'S':
        if allow_save:
            cfg.save_params()
            hw.uart.write('saved\\n')
        else:
            hw.uart.write('busy: stop the car first\\n')
        return None

    if '=' in line:
        k, v = line.split('=', 1)
        k = k.strip()
        try:
            ok = cfg.setp(k, float(v), save=False)
        except ValueError:
            ok = False
        if ok:
            hw.uart.write('ok %s=%s\\n' % (k, cfg.P[k]))
        else:
            hw.uart.write('reject %s\\n' % line)
    return None


def report(angle, target_angle, speed, pwm):
    """遥测。数据从外面传进来，避免和 bc_ctrl 循环引用。"""
    hw.uart.write('%.2f %.2f %.1f %.0f\\n' %
                  (angle, target_angle, speed, pwm))


def say(text):
    hw.uart.write(text)