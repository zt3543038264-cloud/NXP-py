import os

GYRO_LSB = 16.384
RAD2DEG = 57.2958
DT = 0.005
K_FILTER = 0.98
VER = '0812a'
PARAM_FILE = '/flash/pid.txt'
NL = chr(10)
BS = chr(92)

DEFAULTS = {
    'SPD_FF_PWM': 0.0, 'SPD_FF_FULL_ERR': 3.0, 'SPD_FF_ANGLE_ERR': 0.5,
    'MID_ANGLE': 0.7, 'ANG_KP': 5.0, 'ANG_KD': 0.2,
    'RATE_KP': 6.0, 'RATE_KI': 2.0, 'RATE_LIMIT': 1200.0,
    'RATE_I_LIMIT': 2000.0, 'RATE_OUT_LIMIT': 2000.0,
    'MIN_ANGLE': -8.0, 'ANGLE_OFFSET_LIMIT': 2.0,
    'SPD_KP': 5.0, 'SPD_KI': 0.025, 'SPD_I_LIMIT': 100.0,
    'TARGET_SPEED': 20.0, 'MIN_SPEED': 3.0, 'SPD_SLOW': 0.20,
    'SPD_DEC_STEP': 1.0, 'SPD_BRAKE_STEP': 1.0, 'START_HOLD_MS': 300.0,
    'CURVE_ERR': 12.0, 'CURVE_SPEED': 5.0, 'CURVE_DEC_STEP': 1.0,
    'CURVE_BRAKE_STEP': 0.3, 'CURVE_HOLD_N': 10.0,
    'TURN_KP': 49.0, 'TURN_KD': 5.0, 'YAW_HP': 0.0,
    'TURN_LIMIT': 2500.0, 'FAR_WEIGHT': 0.6, 'CROSS_MAX_N': 0.0,
    'FIRST_ANGLE_OUT': 2.0, 'TURN_SLOW': 0.019, 'MIN_LEAN': 0.6,
    'CCD_LOST_MAX': 10.0, 'CCD_STOP_MAX': 50.0, 'DARK_STOP_N': 5.0,
    'ZEBRA_STOP_N': 1.0, 'ZEBRA_STOP_DELAY_MS': 200.0,
    'ZEBRA_BLIND_MS': 3000.0,
    'RAMP_FAR_W': 0.0, 'RAMP_LEAN': 0.5, 'RAMP_MS': 2200.0, 'RAMP_N': 1.0,
    'SPD_CAP': 0.0, 'SPD_BRAKE': 0.0,
    'ANGLE_LIMIT': 40.0, 'DUTY_LIMIT': 8000.0, 'ENC_LIMIT': 20000.0,
    'GYRO_DEAD': 0.0, 'MOTOR_SIGN': 1.0, 'DEAD_DUTY': 0.0,
}

LIMITS = {
    'SPD_FF_PWM': (0.0, 2000.0), 'SPD_FF_FULL_ERR': (0.1, 100.0),
    'SPD_FF_ANGLE_ERR': (0.05, 5.0), 'MID_ANGLE': (-20.0, 20.0),
    'ANG_KP': (0.0, 500.0), 'ANG_KD': (0.0, 50.0),
    'RATE_KP': (0.0, 50.0), 'RATE_KI': (0.0, 5.0),
    'RATE_LIMIT': (10.0, 2000.0), 'RATE_I_LIMIT': (0.0, 8000.0),
    'RATE_OUT_LIMIT': (100.0, 8000.0), 'MIN_ANGLE': (-30.0, 0.0),
    'ANGLE_OFFSET_LIMIT': (0.0, 20.0), 'SPD_KP': (0.0, 50.0),
    'SPD_KI': (0.0, 5.0), 'SPD_I_LIMIT': (0.0, 100000.0),
    'TARGET_SPEED': (-500.0, 500.0), 'MIN_SPEED': (0.0, 500.0),
    'SPD_SLOW': (0.0, 50.0), 'SPD_DEC_STEP': (0.01, 2.0),
    'SPD_BRAKE_STEP': (0.01, 1.0), 'START_HOLD_MS': (0.0, 3000.0),
    'CURVE_ERR': (0.0, 60.0), 'CURVE_SPEED': (0.0, 500.0),
    'CURVE_DEC_STEP': (0.01, 5.0), 'CURVE_BRAKE_STEP': (0.01, 2.0),
    'CURVE_HOLD_N': (0.0, 200.0), 'TURN_KP': (0.0, 500.0),
    'TURN_KD': (0.0, 50.0), 'YAW_HP': (0.0, 1.0),
    'TURN_LIMIT': (0.0, 6000.0), 'FAR_WEIGHT': (0.0, 5.0),
    'CROSS_MAX_N': (0.0, 500.0), 'FIRST_ANGLE_OUT': (0.0, 15.0),
    'TURN_SLOW': (0.0, 1.0), 'MIN_LEAN': (0.0, 5.0),
    'CCD_LOST_MAX': (1.0, 100.0), 'CCD_STOP_MAX': (2.0, 500.0),
    'DARK_STOP_N': (1.0, 200.0), 'ZEBRA_STOP_N': (1.0, 20.0),
    'ZEBRA_STOP_DELAY_MS': (0.0, 3000.0), 'ZEBRA_BLIND_MS': (0.0, 30000.0),
    'RAMP_FAR_W': (0.0, 128.0), 'RAMP_LEAN': (0.0, 10.0),
    'RAMP_MS': (0.0, 10000.0), 'RAMP_N': (1.0, 50.0),
    'SPD_CAP': (0.0, 5000.0), 'SPD_BRAKE': (-3.0, 3.0),
    'ANGLE_LIMIT': (10.0, 60.0), 'DUTY_LIMIT': (0.0, 10000.0),
    'ENC_LIMIT': (100.0, 20000.0), 'GYRO_DEAD': (0.0, 50.0),
    'MOTOR_SIGN': (-1.0, 1.0), 'DEAD_DUTY': (0.0, 2000.0),
}

EXIT_MSG = {1: 'fall down', 2: 'key stop', 3: 'encoder overspeed',
            4: 'remote stop', 5: 'line lost', 6: 'zebra stop',
            7: 'off track (dark)'}
P = dict(DEFAULTS)

def clamp(v, lo, hi):
    if v < lo: return lo
    if v > hi: return hi
    return v

def apply_params():
    global MID_ANGLE, ANG_KP, ANG_KD, RATE_KP, RATE_KI, RATE_LIMIT
    global RATE_I_LIMIT, RATE_OUT_LIMIT, MIN_ANGLE, ANGLE_OFFSET_LIMIT
    global SPD_KP, SPD_KI, SPD_I_LIMIT, TARGET_SPEED, MIN_SPEED, SPD_SLOW
    global SPD_DEC_STEP, SPD_BRAKE_STEP, START_HOLD_MS
    global CURVE_ERR, CURVE_SPEED, CURVE_DEC_STEP, CURVE_BRAKE_STEP, CURVE_HOLD_N
    global TURN_KP, TURN_KD, YAW_HP, TURN_LIMIT, FAR_WEIGHT, CROSS_MAX_N
    global FIRST_ANGLE_OUT, TURN_SLOW, MIN_LEAN
    global CCD_LOST_MAX, CCD_STOP_MAX, DARK_STOP_N
    global ZEBRA_STOP_N, ZEBRA_STOP_DELAY_MS, ZEBRA_BLIND_MS
    global RAMP_FAR_W, RAMP_LEAN, RAMP_MS, RAMP_N
    global SPD_CAP, SPD_BRAKE, ANGLE_LIMIT, DUTY_LIMIT, ENC_LIMIT
    global GYRO_DEAD, MOTOR_SIGN, DEAD_DUTY
    global SPD_FF_PWM, SPD_FF_FULL_ERR, SPD_FF_ANGLE_ERR
    MID_ANGLE=P['MID_ANGLE']; ANG_KP=P['ANG_KP']; ANG_KD=P['ANG_KD']
    RATE_KP=P['RATE_KP']; RATE_KI=P['RATE_KI']; RATE_LIMIT=P['RATE_LIMIT']
    RATE_I_LIMIT=P['RATE_I_LIMIT']; RATE_OUT_LIMIT=P['RATE_OUT_LIMIT']
    MIN_ANGLE=P['MIN_ANGLE']; ANGLE_OFFSET_LIMIT=P['ANGLE_OFFSET_LIMIT']
    SPD_KP=P['SPD_KP']; SPD_KI=P['SPD_KI']; SPD_I_LIMIT=P['SPD_I_LIMIT']
    SPD_FF_PWM=P['SPD_FF_PWM']; SPD_FF_FULL_ERR=P['SPD_FF_FULL_ERR']
    SPD_FF_ANGLE_ERR=P['SPD_FF_ANGLE_ERR']; TARGET_SPEED=P['TARGET_SPEED']
    MIN_SPEED=P['MIN_SPEED']; SPD_SLOW=P['SPD_SLOW']
    SPD_DEC_STEP=P['SPD_DEC_STEP']; SPD_BRAKE_STEP=P['SPD_BRAKE_STEP']
    START_HOLD_MS=int(P['START_HOLD_MS']); CURVE_ERR=P['CURVE_ERR']
    CURVE_SPEED=P['CURVE_SPEED']; CURVE_DEC_STEP=P['CURVE_DEC_STEP']
    CURVE_BRAKE_STEP=P['CURVE_BRAKE_STEP']; CURVE_HOLD_N=int(P['CURVE_HOLD_N'])
    TURN_KP=P['TURN_KP']; TURN_KD=P['TURN_KD']; YAW_HP=P['YAW_HP']
    TURN_LIMIT=P['TURN_LIMIT']; FAR_WEIGHT=P['FAR_WEIGHT']; CROSS_MAX_N=P['CROSS_MAX_N']
    FIRST_ANGLE_OUT=P['FIRST_ANGLE_OUT']; TURN_SLOW=P['TURN_SLOW']; MIN_LEAN=P['MIN_LEAN']
    CCD_LOST_MAX=int(P['CCD_LOST_MAX']); CCD_STOP_MAX=int(P['CCD_STOP_MAX'])
    DARK_STOP_N=int(P['DARK_STOP_N']); ZEBRA_STOP_N=int(P['ZEBRA_STOP_N'])
    ZEBRA_STOP_DELAY_MS=int(P['ZEBRA_STOP_DELAY_MS']); ZEBRA_BLIND_MS=int(P['ZEBRA_BLIND_MS'])
    RAMP_FAR_W=int(P['RAMP_FAR_W']); RAMP_LEAN=P['RAMP_LEAN']
    RAMP_MS=int(P['RAMP_MS']); RAMP_N=int(P['RAMP_N'])
    SPD_CAP=int(P['SPD_CAP']); SPD_BRAKE=P['SPD_BRAKE']
    ANGLE_LIMIT=P['ANGLE_LIMIT']; DUTY_LIMIT=int(P['DUTY_LIMIT'])
    ENC_LIMIT=int(P['ENC_LIMIT']); GYRO_DEAD=int(P['GYRO_DEAD'])
    MOTOR_SIGN=1 if P['MOTOR_SIGN'] >= 0 else -1; DEAD_DUTY=int(P['DEAD_DUTY'])

def load_params():
    try:
        f = open(PARAM_FILE, 'r')
    except OSError:
        print('no param file, using defaults.')
        apply_params()
        return
    with f:
        text = f.read()
    n = 0
    text = text.replace(BS + 'n', NL).replace(chr(13), NL)
    for line in text.split(NL):
        line = line.strip()
        if not line or line[0] == '#' or '=' not in line:
            continue
        k, v = line.split('=', 1)
        k = k.strip()
        if k not in P:
            print('unknown key skipped:', k)
            continue
        try:
            P[k] = float(v); n += 1
        except ValueError:
            print('bad line skipped:', line)
    apply_params()
    print('loaded %d params from %s' % (n, PARAM_FILE))

def save_params():
    tmp = PARAM_FILE + '.tmp'
    with open(tmp, 'w') as f:
        for k in sorted(P):
            f.write('%s=%s' % (k, P[k]) + NL)
    try:
        os.remove(PARAM_FILE)
    except OSError:
        pass
    os.rename(tmp, PARAM_FILE)
    print('params saved.')

def setp(name, value, save=True):
    if name not in P:
        print('unknown param:', name); return False
    v = float(value)
    lo, hi = LIMITS[name]
    if v < lo or v > hi:
        print('out of range: %s=%s (%s~%s)' % (name, v, lo, hi)); return False
    P[name] = v
    apply_params()
    if save: save_params()
    return True

def showp():
    for k in sorted(P):
        print('%-20s = %s' % (k, P[k]))

apply_params()
