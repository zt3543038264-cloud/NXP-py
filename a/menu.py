# 四键屏幕菜单：发车、调参、标定和保存配置。
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

VER = '0807k'

UP, DOWN, OK, BACK = 0, 1, 2, 3      # KEY1 ~ KEY4

ROW_H = 16
VIS   = 12          # 参数页一屏显示几个参数

_shadow = ['~'] * 20

MAIN = ('START  balance', 'PID params', 'IMU calibrate',
        'save to flash', 'load defaults')

ORDER = ('MID_ANGLE', 'BAL_KP', 'BAL_KD',
         'ANG_KP', 'RATE_KP', 'RATE_KI', 'RATE_LIMIT', 'RATE_I_LIMIT',
         'TARGET_SPEED', 'SPD_KP', 'SPD_KI', 'SPD_I_LIMIT',
         'SPD_SLOW', 'MIN_SPEED', 'SPD_DEC_STEP', 'SPD_BRAKE_STEP',
         'TURN_KP', 'TURN_KD', 'YAW_HP', 'CROSS_MAX_N',
         'TURN_LIMIT', 'FAR_WEIGHT',
         'CCD_LOST_MAX',
         'CCD_STOP_MAX', 'ZEBRA_STOP_N', 'ZEBRA_BLIND_MS',
         'ZEBRA_STOP_DELAY_MS', 'DARK_STOP_N',
         'RAMP_FAR_W', 'RAMP_LEAN', 'RAMP_MS', 'RAMP_N',
         'SPD_CAP', 'SPD_BRAKE',
         'TURN_SLOW', 'MIN_LEAN', 'DEAD_DUTY',
         'FIRST_ANGLE_OUT', 'ANGLE_OFFSET_LIMIT',
         'MIN_ANGLE', 'ANGLE_LIMIT', 'DUTY_LIMIT', 'ENC_LIMIT',
         'GYRO_DEAD', 'MOTOR_SIGN')

STEPS = (0.0001, 0.001, 0.01, 0.1, 1.0, 10.0, 100.0)

def _row(i, text):
    """只在内容变了才重画，和 lcd.py 里的 _line 一个道理。"""
    if _shadow[i] == text:
        return
    _shadow[i] = text
    lcd.dev.str16(0, i * ROW_H, '%-30s' % text, 0xFFFF)

def _blank():
    """切页时清屏。"""
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
MIN_GAP      = 120   # 两次有效动作的最小间隔，兜底用
STUCK_MS     = 3000  # 连续报同一个键超过这么久就强制重置状态

_down  = False       # 当前是否处于“按住”状态
_t_up  = 0           # 最近一次读到非 0 的时刻
_t_dn  = 0           # 本次按下的起点
_t_rep = 0           # 上一次连发的时刻
_t_act = 0           # 上一次真正响应的时刻

def _hit():
    """返回本次应该响应的键下标，没有则返回 -1。"""
    global _down, _t_up, _t_dn, _t_rep, _t_act
    v = key.dev.get()
    idx = -1
    for i in range(4):
        if v[i]:
            idx = i
            break
    now = time.ticks_ms()

    if idx < 0:
        if _down and time.ticks_diff(now, _t_up) > HOLD_GAP:
            _down = False
        return -1

    _t_up = now

    if _down and time.ticks_diff(now, _t_dn) > STUCK_MS:
        _down = False

    act = False
    if not _down:                       # 边沿：唯一会立即响应的路径
        _down = True
        _t_dn = now
        _t_rep = now
        act = True
    elif (time.ticks_diff(now, _t_dn) > REPEAT_FIRST
            and time.ticks_diff(now, _t_rep) > REPEAT_GAP):
        _t_rep = now
        act = True

    if not act:
        return -1
    if time.ticks_diff(now, _t_act) < MIN_GAP:
        return -1

    _t_act = now
    key.clear()
    return idx

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
    """改参数只改内存，不写 Flash——和蓝牙调参同一个规矩。"""
    lo, hi = cfg.LIMITS[name]
    cfg.setp(name, cfg.clamp(cfg.P[name] + d, lo, hi), save=False)

def _go():
    """发车。"""
    _blank()
    bt.want = None
    _row(1, 'K4 or BT X = cancel')
    for n in (3, 2, 1):
        _row(0, 'START in %d' % n)
        t = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t) < 1000:
            _pump()
            if _hit() == BACK or bt.want == 'stop':
                bt.want = None
                _toast('canceled')
                return
            time.sleep_ms(2)
    key.clear()
    bt.want = None              # 倒计时里积压的命令一律作废
    _blank()

    try:
        code = balance.run()
    except Exception as e:
        motor.stop()
        name = type(e).__name__
        text = str(e)
        print('RUN CRASHED:', name, text)
        bt.say('crash %s %s' % (name, text) + cfg.NL)
        _blank()
        _row(0, 'RUN CRASHED')
        _row(1, name)
        _row(3, text[:28])
        _row(4, text[28:56])
        _row(6, 'REPL has traceback')
        _row(8, 'any key to return')
        while _hit() < 0:
            _pump()
            time.sleep_ms(5)
        key.clear()
        _blank()
        return

    motor.stop()
    key.clear()
    _blank()
    _row(0, 'EXIT %d' % code)
    _row(1, cfg.EXIT_MSG.get(code, '?'))
    _row(3, 'any key or BT to return')
    while _hit() < 0:
        _pump()
        if bt.want:             # 脱机时手边可能根本没人按键
            break
        time.sleep_ms(5)
    bt.want = None
    key.clear()

def _page_param():
    _blank()
    sel = 0
    top = 0
    si = 4
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
                _row(2 + i, '%s%-19s%10.4f' % (mark, nm, cfg.P[nm]))
            if editing:
                _row(15, 'K1 +      K2 -')
                _row(16, 'K3 step   K4 done')
            else:
                _row(15, 'K1 up     K2 down')
                _row(16, 'K3 edit   K4 back')
            _row(18, 'ram only, save on main')
        time.sleep_ms(2)

def _recal():
    """重新标定陀螺零偏。"""
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
    bt.want = None              # 丢掉进菜单之前积压的命令
    sel = 0
    shown = -1                  # 已经画在屏上的光标位置
    t0 = 0
    while True:
        _pump()

        if bt.want == 'go':     # 蓝牙发车，等同选中第一项按 KEY3
            bt.want = None
            _go()
            _blank()
            shown = -1
        elif bt.want:
            bt.want = None      # 菜单里收到 stop 之类，吃掉即可

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