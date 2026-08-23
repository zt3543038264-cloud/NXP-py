import time
import cfg, key, imu, enc, motor, tick, bt, lcd, balance

VER = '0812a'
UP, DOWN, OK, BACK = 0, 1, 2, 3
ROW_H = 16
VIS = 12
_shadow = ['~'] * 20
MAIN = ('START  track', 'START  balance only', 'PID params',
        'IMU calibrate', 'save to flash', 'load defaults')
ORDER = ('MID_ANGLE','ANG_KP','ANG_KD','RATE_KP','RATE_KI','RATE_LIMIT','RATE_OUT_LIMIT',
         'MIN_ANGLE','ANGLE_OFFSET_LIMIT','SPD_KP','SPD_KI','SPD_FF_PWM',
         'SPD_FF_FULL_ERR','SPD_FF_ANGLE_ERR','SPD_I_LIMIT','TARGET_SPEED',
         'MIN_SPEED','SPD_SLOW','SPD_DEC_STEP','SPD_BRAKE_STEP','START_HOLD_MS',
         'CURVE_ERR','CURVE_SPEED','CURVE_DEC_STEP','CURVE_BRAKE_STEP','CURVE_HOLD_N',
         'TURN_KP','TURN_KD','YAW_HP','TURN_LIMIT','FAR_WEIGHT','CROSS_MAX_N',
         'FIRST_ANGLE_OUT','TURN_SLOW','MIN_LEAN','CCD_LOST_MAX','CCD_STOP_MAX',
         'DARK_STOP_N','ZEBRA_STOP_N','ZEBRA_STOP_DELAY_MS','ZEBRA_BLIND_MS',
         'RAMP_FAR_W','RAMP_LEAN','RAMP_MS','RAMP_N','SPD_CAP','SPD_BRAKE',
         'ANGLE_LIMIT','DUTY_LIMIT','ENC_LIMIT','GYRO_DEAD','MOTOR_SIGN','DEAD_DUTY')
STEPS = (0.0001,0.001,0.01,0.1,1.0,10.0,100.0)

def _row(i, text):
    if _shadow[i] == text: return
    _shadow[i] = text
    lcd.dev.str16(0, i * ROW_H, '%-30s' % text, 0xFFFF)

def _blank():
    lcd.dev.clear()
    for i in range(20): _shadow[i] = '~'
    for i in range(5): lcd._last[i] = '~'

def _pump():
    if tick.flag5:
        tick.flag5 = False; imu.update(); key.dev.capture()
    if tick.flag20:
        tick.flag20 = False; enc.update(); bt.poll(allow_save=True)

HOLD_GAP=50; REPEAT_FIRST=500; REPEAT_GAP=200; MIN_GAP=120; STUCK_MS=3000
_down=False; _t_up=0; _t_dn=0; _t_rep=0; _t_act=0

def _hit():
    global _down,_t_up,_t_dn,_t_rep,_t_act
    v=key.dev.get(); idx=-1
    for i in range(4):
        if v[i]: idx=i; break
    now=time.ticks_ms()
    if idx<0:
        if _down and time.ticks_diff(now,_t_up)>HOLD_GAP: _down=False
        return -1
    _t_up=now
    if _down and time.ticks_diff(now,_t_dn)>STUCK_MS: _down=False
    act=False
    if not _down:
        _down=True; _t_dn=now; _t_rep=now; act=True
    elif time.ticks_diff(now,_t_dn)>REPEAT_FIRST and time.ticks_diff(now,_t_rep)>REPEAT_GAP:
        _t_rep=now; act=True
    if not act or time.ticks_diff(now,_t_act)<MIN_GAP: return -1
    _t_act=now; key.clear(); return idx

def _wait_ms(ms):
    t=time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(),t)<ms:
        _pump(); time.sleep_ms(2)

def _toast(a,b='',ms=900):
    _blank(); _row(0,a); _row(1,b); _wait_ms(ms); _blank()

def _bump(name,d):
    lo,hi=cfg.LIMITS[name]
    cfg.setp(name,cfg.clamp(cfg.P[name]+d,lo,hi),save=False)

def _go(track=True):
    _blank(); bt.want=None; _row(1,'K4 or BT X = cancel')
    label='TRACK' if track else 'BALANCE'
    for n in (3,2,1):
        _row(0,'%s in %d'%(label,n)); t=time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(),t)<1000:
            _pump()
            if _hit()==BACK or bt.want=='stop':
                bt.want=None; _toast('canceled'); return
            time.sleep_ms(2)
    key.clear(); bt.want=None; _blank()
    try:
        code=balance.run(track)
    except Exception as e:
        motor.stop(); _toast('RUN CRASHED',type(e).__name__,1500); return
    motor.stop(); key.clear(); _blank()
    _row(0,'EXIT %d'%code); _row(1,cfg.EXIT_MSG.get(code,'?'))
    while _hit()<0:
        _pump()
        if bt.want: break
        time.sleep_ms(5)
    bt.want=None; key.clear()

def _page_param():
    _blank(); sel=0; top=0; si=4; editing=False; dirty=True
    while True:
        _pump(); k=_hit()
        if k>=0: dirty=True
        if editing:
            name=ORDER[sel]
            if k==UP: _bump(name,STEPS[si])
            elif k==DOWN: _bump(name,-STEPS[si])
            elif k==OK: si=(si+1)%len(STEPS)
            elif k==BACK: editing=False
        else:
            if k==UP: sel=(sel-1)%len(ORDER)
            elif k==DOWN: sel=(sel+1)%len(ORDER)
            elif k==OK: editing=True
            elif k==BACK: return
        if sel<top: top=sel
        elif sel>=top+VIS: top=sel-VIS+1
        if dirty:
            dirty=False; _row(0,'EDIT step %s'%STEPS[si] if editing else 'PID PARAMS (ram)')
            for i in range(VIS):
                n=top+i
                if n>=len(ORDER): _row(2+i,''); continue
                mark='*' if editing and n==sel else ('>' if n==sel else ' ')
                _row(2+i,'%s%-19s%10.4f'%(mark,ORDER[n],cfg.P[ORDER[n]]))
        time.sleep_ms(2)

def _recal():
    _blank(); _row(0,'keep the car still'); _row(1,'calibrating ...')
    tick.stop(); imu.calibrate(); tick.start(); key.clear()
    _toast('bias %.2f'%imu.gy_bias,'ang %.2f'%imu.angle,1500)

def _defaults():
    _blank(); _row(0,'load DEFAULTS ?'); _row(1,'K3 = yes other = no')
    while True:
        _pump(); k=_hit()
        if k==OK:
            for n in cfg.DEFAULTS: cfg.P[n]=cfg.DEFAULTS[n]
            cfg.apply_params(); _toast('defaults loaded','not saved yet',1200); return
        if k>=0: _toast('canceled'); return
        time.sleep_ms(5)

def _page_main():
    _blank(); bt.want=None; sel=0; shown=-1; t0=0
    while True:
        _pump()
        if bt.want=='go': bt.want=None; _go(True); _blank(); shown=-1
        elif bt.want=='go_balance': bt.want=None; _go(False); _blank(); shown=-1
        elif bt.want: bt.want=None
        k=_hit()
        if k==UP: sel=(sel-1)%len(MAIN)
        elif k==DOWN: sel=(sel+1)%len(MAIN)
        elif k==OK:
            if sel==0: _go(True)
            elif sel==1: _go(False)
            elif sel==2: _page_param()
            elif sel==3: _recal()
            elif sel==4: cfg.save_params(); _toast('saved',cfg.PARAM_FILE,1200)
            else: _defaults()
            _blank(); shown=-1
        if sel!=shown:
            shown=sel; _row(0,'== MAIN MENU ==')
            for i,x in enumerate(MAIN): _row(2+i,('> ' if i==sel else '  ')+x)
        if time.ticks_diff(time.ticks_ms(),t0)>150:
            t0=time.ticks_ms(); _row(8,'ang %8.2f deg'%imu.angle)
            _row(9,'rate %8.2f dps'%imu.rate); _row(10,'encL %8d'%enc.left)
            _row(11,'encR %8d'%enc.right); _row(12,'spd %8.1f'%enc.speed)
        time.sleep_ms(2)

def main():
    cfg.load_params(); cfg.showp(); print('calibrating, keep the car still ...')
    imu.calibrate(); tick.start(); key.clear()
    try: _page_main()
    except KeyboardInterrupt: pass
    finally:
        tick.stop(); motor.stop(); _blank(); _row(0,'menu stopped')
