# menu.py —— 屏幕四键菜单。发车、改参数、看传感器都在这里。
# 依赖方向：menu -> balance -> 其他外设。没有人 import menu，不会成环。
import time

import cfg
import key
import imu
import enc
import motor
import tick
import bt
import lcd
import balance

UP, DOWN, OK, BACK = 0, 1, 2, 3      # KEY1 ~ KEY4

ROW_H = 16          # str16 字高。240x320 屏最多 20 行、每行 30 字
VIS   = 12          # 参数页一屏显示几个参数

_shadow = ['~'] * 20

MAIN = ('START  balance', 'PID params', 'IMU calibrate',
        'save to flash', 'load defaults')

# 调参顺序按「用到的先后」排，不是字母序
ORDER = ('MID_ANGLE', 'BAL_KP', 'BAL_KD', 'SPD_KP', 'SPD_KI',
         'TARGET_SPEED', 'FIRST_ANGLE_OUT', 'ANGLE_OFFSET_LIMIT',
         'MIN_ANGLE', 'ANGLE_LIMIT', 'DUTY_LIMIT', 'ENC_LIMIT',
         'GYRO_DEAD', 'MOTOR_SIGN')

STEPS = (0.01, 0.1, 1.0, 10.0, 100.0)


def _row(i, text):
    """只在内容变了才重画，和 lcd.py 里的 _line 一个道理。"""
    if _shadow[i] == text:
        return
    _shadow[i] = text
    lcd.dev.str16(0, i * ROW_H, '%-30s' % text, 0xFFFF)


def _blank():
    """切页时清屏。必须同时作废 lcd.py 自己的行缓存，
    否则两套缓存会互相欺骗：屏幕已经被清空，缓存却以为字还在。"""
    lcd.dev.clear()
    for i in range(20):
        _shadow[i] = '~'
    for i in range(5):
        lcd._last[i] = '~'


def _pump():
    """菜单里也要处理 ticker 标志，否则角度不刷新、蓝牙不响应。"""
    if tick.flag5:
        tick.flag5 = False
        imu.update()
    if tick.flag20:
        tick.flag20 = False
        enc.update()
        bt.poll(allow_save=True)     # 菜单里等同 idle，允许远程存盘


HOLD_GAP     = 50    # 连续多少 ms 读到全 0 才算真的松手
REPEAT_FIRST = 500   # 按住多久开始连发
REPEAT_GAP   = 200   # 连发间隔

_down  = False       # 当前是否处于“按住”状态
_t_up  = 0           # 最近一次读到非 0 的时刻
_t_dn  = 0           # 本次按下的起点
_t_rep = 0           # 上一次连发的时刻


def _hit():
    """返回本次应该响应的键下标，没有则返回 -1。

    只在 0 -> 1 边沿响应一次，按住不放 0.5 s 后每 0.2 s 连发。
    直接拿 `if v[i]` 当按键事件是错的：主循环 2 ms 一圈，手指再快也要
    按住 ≈100 ms，一下会被当成几十次，光标直接飞出去。
    """
    global _down, _t_up, _t_dn, _t_rep
    v = key.dev.get()
    idx = -1
    for i in range(4):
        if v[i]:
            idx = i
            break
    now = time.ticks_ms()

    if idx < 0:
        # 按住期间也可能间歇读到 0（扫描相位 + clear 的竞争），
        # 所以要连续 HOLD_GAP 内都是 0 才能判定为松手。
        if _down and time.ticks_diff(now, _t_up) > HOLD_GAP:
            _down = False
        return -1

    _t_up = now
    key.clear()

    if not _down:                       # 边沿：唯一会立即响应的路径
        _down = True
        _t_dn = now
        _t_rep = now
        return idx

    if (time.ticks_diff(now, _t_dn) > REPEAT_FIRST
            and time.ticks_diff(now, _t_rep) > REPEAT_GAP):
        _t_rep = now
        return idx

    return -1


def _wait_ms(ms):
    t = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t) < ms:
        _pump()
        time.sleep_ms(2)


def _toast(line1, line2='', ms=900):
    _blank()
    _row(0, line1)
    _row(1, line2)
    _wait_ms(ms)
    _blank()


def _bump(name, d):
    """改参数只改内存，不写 Flash——和蓝牙调参同一个规矩。
    先夹到 LIMITS 范围内再 setp，所以永远不会被 reject。"""
    lo, hi = cfg.LIMITS[name]
    cfg.setp(name, cfg.clamp(cfg.P[name] + d, lo, hi), save=False)


def _go():
    """发车。倒数 3 秒，期间 KEY4 可以取消。"""
    _blank()
    _row(1, 'K4 = cancel')
    for n in (3, 2, 1):
        _row(0, 'START in %d' % n)
        t = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t) < 1000:
            _pump()
            if _hit() == BACK:
                _toast('canceled')
                return
            time.sleep_ms(2)
    key.clear()
    _blank()

    code = balance.run()        # 阻塞：倒地 / KEY2 / 飞车 / 远程 X 才返回

    motor.stop()
    key.clear()
    _blank()
    _row(0, 'EXIT %d' % code)
    _row(1, cfg.EXIT_MSG.get(code, '?'))
    _row(3, 'any key to return')
    while _hit() < 0:
        _pump()
        time.sleep_ms(5)
    key.clear()


def _page_param():
    _blank()
    sel = 0
    top = 0
    si = 2                      # 默认步长 1.0
    editing = False
    dirty = True
    while True:
        _pump()
        k = _hit()
        if k >= 0:
            dirty = True        # 这一页只有按键会改变内容，没按就一个字节都不发

        if editing:
            name = ORDER[sel]
            if k == UP:
                _bump(name, STEPS[si])
            elif k == DOWN:
                _bump(name, -STEPS[si])
            elif k == OK:
                si = (si + 1) % len(STEPS)
            elif k == BACK:
                editing = False
        else:
            if k == UP:
                sel = (sel - 1) % len(ORDER)
            elif k == DOWN:
                sel = (sel + 1) % len(ORDER)
            elif k == OK:
                editing = True
            elif k == BACK:
                return

        if sel < top:
            top = sel
        elif sel >= top + VIS:
            top = sel - VIS + 1

        if dirty:
            dirty = False
            if editing:
                _row(0, 'EDIT   step %s' % STEPS[si])
            else:
                _row(0, 'PID PARAMS   (ram)')
            for i in range(VIS):
                n = top + i
                if n >= len(ORDER):
                    _row(2 + i, '')
                    continue
                nm = ORDER[n]
                if n != sel:
                    mark = ' '
                elif editing:
                    mark = '*'
                else:
                    mark = '>'
                _row(2 + i, '%s%-19s%8.2f' % (mark, nm, cfg.P[nm]))
            if editing:
                _row(15, 'K1 +      K2 -')
                _row(16, 'K3 step   K4 done')
            else:
                _row(15, 'K1 up     K2 down')
                _row(16, 'K3 edit   K4 back')
            _row(18, 'ram only, save on main')
        time.sleep_ms(2)


def _recal():
    """重新标定陀螺零偏。标定用的是 read()，先把 ticker 停掉别抢采集。"""
    _blank()
    _row(0, 'keep the car still')
    _row(1, 'calibrating ...')
    tick.stop()
    imu.calibrate()
    tick.start()
    key.clear()
    _toast('bias %.2f' % imu.gy_bias, 'ang  %.2f' % imu.angle, 1500)


def _defaults():
    _blank()
    _row(0, 'load DEFAULTS ?')
    _row(1, 'K3 = yes   other = no')
    while True:
        _pump()
        k = _hit()
        if k == OK:
            for n in cfg.DEFAULTS:
                cfg.P[n] = cfg.DEFAULTS[n]
            cfg.apply_params()
            _toast('defaults loaded', 'not saved yet', 1200)
            return
        if k >= 0:
            _toast('canceled')
            return
        time.sleep_ms(5)


def _page_main():
    _blank()
    sel = 0
    shown = -1                  # 已经画在屏上的光标位置
    t0 = 0
    while True:
        _pump()
        k = _hit()
        if k == UP:
            sel = (sel - 1) % len(MAIN)
        elif k == DOWN:
            sel = (sel + 1) % len(MAIN)
        elif k == OK:
            if sel == 0:
                _go()
            elif sel == 1:
                _page_param()
            elif sel == 2:
                _recal()
            elif sel == 3:
                cfg.save_params()
                _toast('saved', cfg.PARAM_FILE, 1200)
            else:
                _defaults()
            _blank()
            shown = -1          # _blank() 后缓存已作废，强制重画菜单行
        # KEY4 在主菜单不做事，防止误触退出

        # 菜单行只在光标动了才重排，和实时数据分开，先保证按键跟手
        if sel != shown:
            shown = sel
            _row(0, '== MAIN MENU ==')
            for i in range(len(MAIN)):
                if i == sel:
                    _row(2 + i, '> ' + MAIN[i])
                else:
                    _row(2 + i, '  ' + MAIN[i])
            _row(14, 'K1 up     K2 down')
            _row(15, 'K3 enter')

        # 首页就是仪表盘：第 3 步读机械零点、第 2 步看推车计数都看这里
        if time.ticks_diff(time.ticks_ms(), t0) > 150:
            t0 = time.ticks_ms()
            _row(8,  'ang  %8.2f deg' % imu.angle)
            _row(9,  'rate %8.2f dps' % imu.rate)
            _row(10, 'encL %8d' % enc.left)
            _row(11, 'encR %8d' % enc.right)
            _row(12, 'spd  %8.1f' % enc.speed)
        time.sleep_ms(2)


def main():
    cfg.load_params()
    cfg.showp()
    print('calibrating, keep the car still ...')
    imu.calibrate()
    print('gy_bias = %.3f   angle0 = %.2f' % (imu.gy_bias, imu.angle))
    tick.start()
    key.clear()
    try:
        _page_main()
    except KeyboardInterrupt:
        pass
    finally:
        tick.stop()
        motor.stop()
        _blank()
        _row(0, 'menu stopped')
        print('menu stopped.')