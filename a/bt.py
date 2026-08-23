# 蓝牙串口协议：接收控制/调参命令并发送遥测。
import time
from machine import UART

import cfg

uart = UART(2)
uart.init(9600, bits=8, parity=None, stop=1)

NL = chr(10)
CR = chr(13)

VER = '0812a'

IDLE_MS = 150
_buf = ''
_t_rx = 0
want = None

def say(text):
    uart.write(text)

def test(baud=None):
    import time
    if baud:
        uart.init(baud, bits=8, parity=None, stop=1)
    for i in range(20):
        uart.write('bt ok %d' % i + NL)
        n = uart.any()
        if n:
            print('rx:', uart.read(n))
        time.sleep_ms(500)

def report(angle, target_angle, err, pwm, lost=0):
    uart.write('%.2f %.2f %.1f %.0f %d'
               % (angle, target_angle, err, pwm, lost) + NL)

def _run_cmd(line, allow_save):
    global want
    if line == 'X':
        want = 'stop'
        uart.write('stopping' + NL)
        return 'stop'
    if line == 'G':
        want = 'go'
        uart.write('go' + NL)
        return 'go'
    if line == 'H':
        want = 'go_balance'
        uart.write('go balance' + NL)
        return 'go_balance'
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
    uart.write('unknown ' + line + NL)
    return None

def poll(allow_save=False):
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
        if len(_buf) > 200:
            _buf = ''
            return None
    if NL in _buf:
        line, _buf = _buf.split(NL, 1)
    elif _buf and time.ticks_diff(time.ticks_ms(), _t_rx) > IDLE_MS:
        line = _buf
        _buf = ''
    else:
        return None
    line = line.strip()
    if not line:
        return None
    return _run_cmd(line, allow_save)
