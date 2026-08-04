# bt.py —— 蓝牙/无线串口文本协议。没接模块时也能安全跑，写出去没人收而已。
import time
from machine import UART

import cfg

# LPUART3 = C6/C7。波特率必须和模块实际配置一致。
# 2026-08-03 btscan.py 实测：本模块为 9600（其余四档全是乱码）。
uart = UART(2)
uart.init(9600, bits=8, parity=None, stop=1)

# 全文用 chr(10) / chr(13)，一个反斜杠转义都不写。
# 这样从网页或聊天里复制过去永远不会被转义规则改坏。
NL = chr(10)
CR = chr(13)

IDLE_MS = 150      # 最后一个字节之后静默这么久，就当一条命令收完了

_buf = ''
_t_rx = 0

# 由使用方消费后必须清空。用模块级变量而不是只靠 poll() 的返回值，
# 是因为菜单的 _pump() 会丢弃返回值，而 balance.run() 只关心 'stop'。
want = None


def say(text):
    uart.write(text)


def test(baud=None):
    """接上模块后先跑这个。手机串口 App 应每 0.5 s 收到一行，
    发回来的任何内容会打印在 REPL。波特率对不上就是一堆乱码。
    例：bt.test(9600)
    """
    import time
    if baud:
        uart.init(baud, bits=8, parity=None, stop=1)
    for i in range(20):
        uart.write('bt ok %d\n' % i)
        n = uart.any()
        if n:
            print('rx:', uart.read(n))
        time.sleep_ms(500)


def report(angle, target_angle, speed, pwm):
    """遥测。数据从外面传进来，避免反过来 import balance 造成循环引用。"""
    uart.write('%.2f %.2f %.1f %.0f\\n' % (angle, target_angle, speed, pwm))


def _run_cmd(line, allow_save):
    global want

    if line == 'X':
        want = 'stop'
        uart.write('stopping' + NL)
        return 'stop'

    if line == 'G':          # 发车。等同菜单里按 KEY1，照旧有 3 秒倒计时
        want = 'go'
        uart.write('go' + NL)
        return 'go'

    if line == '?':
        for k in sorted(cfg.P):
            uart.write('%s=%s' % (k, cfg.P[k]) + NL)
        return None

    if line == 'S':
        if allow_save:
            cfg.save_params()
            uart.write('saved' + NL)
        else:
            uart.write('busy: stop the car first' + NL)
        return None

    if '=' in line:
        k, v = line.split('=', 1)
        k = k.strip()
        try:
            ok = cfg.setp(k, float(v), save=False)
        except ValueError:
            ok = False
        if ok:
            uart.write('ok %s=%s' % (k, cfg.P[k]) + NL)
        else:
            uart.write('reject ' + line + NL)
        return None

    uart.write('unknown ' + line + NL)   # 有回应总好过沉默
    return None


def poll(allow_save=False):
    """非阻塞。返回 'stop' 表示远程停车，否则 None。

    协议：一行一条
        BAL_KP=260   改参数（只改内存，立即生效）
        ?            回传全部参数
        S            存盘（仅 idle 时允许）
        X            远程停车

    【行结尾】2026-08-03 实测：手机串口 App 发 '?' 时只有 1 个字节，
    不带任何行结尾。所以不能只认换行，三种结束条件都接受：
        ① 收到 chr(10)
        ② 收到 chr(13)（进来时统一替换成 chr(10)）
        ③ 静默超过 IDLE_MS 毫秒（App 根本不追加行结尾时靠这条）
    代价是不带行结尾时命令晚 150 ms 执行，调参完全无感。
    """
    global _buf, _t_rx
    n = uart.any()
    if n:
        try:
            s = uart.read(n).decode()
        except Exception:
            _buf = ''
            return None
        _buf += s.replace(CR, NL)
        _t_rx = time.ticks_ms()
        if len(_buf) > 200:        # 收到乱码时防止无限增长
            _buf = ''
            return None

    if NL in _buf:
        line, _buf = _buf.split(NL, 1)
    elif _buf and time.ticks_diff(time.ticks_ms(), _t_rx) > IDLE_MS:
        line = _buf                # 没有行结尾，靠静默判定收完
        _buf = ''
    else:
        return None

    line = line.strip()
    if not line:
        return None
    return _run_cmd(line, allow_save)