# 集中管理控制参数、范围校验及 Flash 读写。
import os

# ---- 硬件常量（实测得出，不要改） ----
GYRO_LSB = 16.384          # ±2000dps
RAD2DEG  = 57.2958
DT       = 0.005           # 直立环周期 (s)
K_FILTER = 0.98            # 互补滤波系数

VER = '0807k'

PARAM_FILE = '/flash/pid.txt'

NL = chr(10)
BS = chr(92)      # 反斜杠本人，修复旧的坏文件时要用

DEFAULTS = {
    'MID_ANGLE': 9.0,
    'BAL_KP': 450.0,            # 直立环 P（并联版；串级启用后为死参数，保留可回退）
    'BAL_KD': 2.0,              # 直立环 D（同上）
    'ANG_KP': 225.0,            # 角度环 P：偏 1 度要求多少 deg/s 回正角速度
    'RATE_KP': 2.0,             # 角速度环 P
    'RATE_KI': 0.0,             # 角速度环 I，先 0
    'RATE_LIMIT': 1200.0,       # 目标角速度限幅 deg/s（等价验收期间等于关闭）
    'RATE_I_LIMIT': 2000.0,     # 角速度环积分限幅
    # ---- 速度环 ----
    'SPD_KP': 0.10,             # 速度环 P：配合目标斜坡，负责即时纠偏
    'SPD_KI': 0.006,
    'TARGET_SPEED': 7.0,
    'SPD_I_LIMIT': 100.0,
    'SPD_SLOW': 0.20,
    'MIN_SPEED': 3.0,
    'SPD_DEC_STEP': 0.35,
    'SPD_BRAKE_STEP': 0.15,
    'FIRST_ANGLE_OUT': 1.6,
    'ANGLE_OFFSET_LIMIT': 2.0,
    'MIN_ANGLE': -8.0,          # 目标角下限
    'ANGLE_LIMIT': 40.0,        # 倒地保护角
    'DUTY_LIMIT': 8000.0,       # 占空比限幅
    'ENC_LIMIT': 20000.0,
    'GYRO_DEAD': 0.0,           # 陀螺死区 (LSB)
    'MOTOR_SIGN': 1.0,          # 整体极性
    'TURN_KP': 49.0,        # 转向环 P：小误差保持直道稳定，大误差由平方项增强
    'TURN_KD': 5.0,
    'YAW_HP': 0.0,
    'CROSS_MAX_N': 0.0,
    'TURN_LIMIT': 2500.0,   # 差动限幅，别让转向吃掉全部直立余量
    'FAR_WEIGHT': 0.6,
    'CCD_LOST_MAX': 10.0,
    'CCD_STOP_MAX': 50.0,
    'ZEBRA_STOP_N': 1.0,
    'ZEBRA_STOP_DELAY_MS': 100.0,
    'ZEBRA_BLIND_MS': 3000.0,
    'TURN_SLOW': 0.019,
    'MIN_LEAN': 0.6,
    'DEAD_DUTY': 0.0,
    'DARK_STOP_N': 5.0,
    # ---- 坡道 ----
    'RAMP_FAR_W': 0.0,
    'RAMP_LEAN': 1.5,
    'RAMP_MS': 1500.0,
    'RAMP_N': 3.0,
    # ---- 限速 ----
    'SPD_CAP': 8.5,
    'SPD_BRAKE': -0.8,
}

LIMITS = {
    'MID_ANGLE':          (-20.0, 20.0),
    'BAL_KP':             (0.0, 2000.0),
    'BAL_KD':             (0.0, 200.0),
    'ANG_KP':             (0.0, 500.0),
    'RATE_KP':            (0.0, 50.0),
    'RATE_KI':            (0.0, 5.0),
    'RATE_LIMIT':         (10.0, 2000.0),
    'RATE_I_LIMIT':       (0.0, 8000.0),
    'SPD_KP':             (0.0, 50.0),
    'SPD_KI':             (0.0, 5.0),
    'TARGET_SPEED':       (-500.0, 500.0),
    'SPD_I_LIMIT':        (0.0, 100000.0),
    'SPD_SLOW':           (0.0, 50.0),
    'MIN_SPEED':          (0.0, 500.0),
    'SPD_DEC_STEP':       (0.01, 2.0),
    'SPD_BRAKE_STEP':     (0.01, 1.0),
    'FIRST_ANGLE_OUT':    (0.0, 15.0),
    'ANGLE_OFFSET_LIMIT': (0.0, 20.0),
    'MIN_ANGLE':          (-30.0, 0.0),
    'ANGLE_LIMIT':        (10.0, 60.0),
    'DUTY_LIMIT':         (0.0, 10000.0),
    'ENC_LIMIT':          (100.0, 20000.0),
    'GYRO_DEAD':          (0.0, 50.0),
    'MOTOR_SIGN':         (-1.0, 1.0),
    'TURN_KP':            (0.0, 500.0),
    'TURN_KD':            (0.0, 50.0),
    'YAW_HP':             (0.0, 1.0),
    'CROSS_MAX_N':        (0.0, 500.0),
    'TURN_LIMIT':         (0.0, 6000.0),
    'FAR_WEIGHT':         (0.0, 5.0),
    'CCD_LOST_MAX':       (1.0, 100.0),
    'CCD_STOP_MAX':       (2.0, 500.0),
    'ZEBRA_STOP_N':       (1.0, 20.0),
    'TURN_SLOW':          (0.0, 1.0),
    'MIN_LEAN':           (0.0, 5.0),
    'DEAD_DUTY':          (0.0, 2000.0),
    'ZEBRA_BLIND_MS':     (0.0, 30000.0),
    'ZEBRA_STOP_DELAY_MS': (0.0, 3000.0),
    'DARK_STOP_N':        (1.0, 200.0),
    'RAMP_FAR_W':         (0.0, 128.0),
    'RAMP_LEAN':          (0.0, 10.0),
    'RAMP_MS':            (0.0, 10000.0),
    'RAMP_N':             (1.0, 50.0),
    'SPD_CAP':            (0.0, 5000.0),
    'SPD_BRAKE':          (-3.0, 3.0),
}

EXIT_MSG = {1: 'fall down', 2: 'key stop', 3: 'encoder overspeed',
            4: 'remote stop', 5: 'line lost', 6: 'zebra stop',
            7: 'off track (dark)'}

P = dict(DEFAULTS)

CROSS_MAX_N = 0.0

MID_ANGLE = BAL_KP = BAL_KD = SPD_KP = SPD_KI = 0.0
ANG_KP = RATE_KP = RATE_KI = RATE_LIMIT = RATE_I_LIMIT = 0.0
TARGET_SPEED = FIRST_ANGLE_OUT = ANGLE_OFFSET_LIMIT = MIN_ANGLE = 0.0
ANGLE_LIMIT = 40.0
DUTY_LIMIT = ENC_LIMIT = GYRO_DEAD = MOTOR_SIGN = 0
TURN_KP = TURN_KD = TURN_LIMIT = FAR_WEIGHT = CCD_LOST_MAX = 0.0
CCD_STOP_MAX = ZEBRA_STOP_N = 0
TURN_SLOW = MIN_LEAN = 0.0
DEAD_DUTY = ZEBRA_BLIND_MS = ZEBRA_STOP_DELAY_MS = DARK_STOP_N = 0
RAMP_FAR_W = RAMP_MS = RAMP_N = 0
RAMP_LEAN = 0.0
SPD_CAP = 0
SPD_BRAKE = 0.0
SPD_I_LIMIT = SPD_SLOW = MIN_SPEED = 0.0
SPD_DEC_STEP = SPD_BRAKE_STEP = 0.0
YAW_HP = 0.0

def clamp(v, lo, hi):
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v

def apply_params():
    global MID_ANGLE, BAL_KP, BAL_KD, SPD_KP, SPD_KI
    global ANG_KP, RATE_KP, RATE_KI, RATE_LIMIT, RATE_I_LIMIT
    global TARGET_SPEED, FIRST_ANGLE_OUT, ANGLE_OFFSET_LIMIT, MIN_ANGLE
    global ANGLE_LIMIT, DUTY_LIMIT, ENC_LIMIT, GYRO_DEAD, MOTOR_SIGN
    global TURN_KP, TURN_KD, TURN_LIMIT, FAR_WEIGHT, CCD_LOST_MAX
    global CCD_STOP_MAX, ZEBRA_STOP_N, TURN_SLOW, MIN_LEAN, DEAD_DUTY
    global ZEBRA_BLIND_MS, ZEBRA_STOP_DELAY_MS, DARK_STOP_N
    global RAMP_FAR_W, RAMP_LEAN, RAMP_MS, RAMP_N
    global SPD_CAP, SPD_BRAKE
    global SPD_I_LIMIT, SPD_SLOW, MIN_SPEED
    global SPD_DEC_STEP, SPD_BRAKE_STEP
    global YAW_HP
    global CROSS_MAX_N
    CROSS_MAX_N        = P['CROSS_MAX_N']
    MID_ANGLE          = P['MID_ANGLE']
    BAL_KP             = P['BAL_KP']
    BAL_KD             = P['BAL_KD']
    ANG_KP             = P['ANG_KP']
    RATE_KP            = P['RATE_KP']
    RATE_KI            = P['RATE_KI']
    RATE_LIMIT         = P['RATE_LIMIT']
    RATE_I_LIMIT       = P['RATE_I_LIMIT']
    SPD_KP             = P['SPD_KP']
    SPD_KI             = P['SPD_KI']
    TARGET_SPEED       = P['TARGET_SPEED']
    FIRST_ANGLE_OUT    = P['FIRST_ANGLE_OUT']
    ANGLE_OFFSET_LIMIT = P['ANGLE_OFFSET_LIMIT']
    MIN_ANGLE          = P['MIN_ANGLE']
    ANGLE_LIMIT        = P['ANGLE_LIMIT']
    DUTY_LIMIT         = int(P['DUTY_LIMIT'])
    ENC_LIMIT          = int(P['ENC_LIMIT'])
    GYRO_DEAD          = int(P['GYRO_DEAD'])
    MOTOR_SIGN         = 1 if P['MOTOR_SIGN'] >= 0 else -1
    TURN_KP            = P['TURN_KP']
    TURN_KD            = P['TURN_KD']
    TURN_LIMIT         = P['TURN_LIMIT']
    FAR_WEIGHT         = P['FAR_WEIGHT']
    CCD_LOST_MAX       = int(P['CCD_LOST_MAX'])
    CCD_STOP_MAX       = int(P['CCD_STOP_MAX'])
    ZEBRA_STOP_N       = int(P['ZEBRA_STOP_N'])
    TURN_SLOW          = P['TURN_SLOW']
    MIN_LEAN           = P['MIN_LEAN']
    DEAD_DUTY          = int(P['DEAD_DUTY'])
    ZEBRA_BLIND_MS     = int(P['ZEBRA_BLIND_MS'])
    ZEBRA_STOP_DELAY_MS = int(P['ZEBRA_STOP_DELAY_MS'])
    DARK_STOP_N        = int(P['DARK_STOP_N'])
    RAMP_FAR_W         = int(P['RAMP_FAR_W'])
    RAMP_LEAN          = P['RAMP_LEAN']
    RAMP_MS            = int(P['RAMP_MS'])
    RAMP_N             = int(P['RAMP_N'])
    SPD_CAP            = int(P['SPD_CAP'])
    SPD_BRAKE          = P['SPD_BRAKE']
    SPD_I_LIMIT        = P['SPD_I_LIMIT']
    SPD_SLOW           = P['SPD_SLOW']
    MIN_SPEED          = P['MIN_SPEED']
    SPD_DEC_STEP       = P['SPD_DEC_STEP']
    SPD_BRAKE_STEP     = P['SPD_BRAKE_STEP']
    YAW_HP             = P['YAW_HP']

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
            P[k] = float(v)
            n += 1
        except ValueError:
            print('bad line skipped:', line)
    apply_params()
    print('loaded %d params from %s' % (n, PARAM_FILE))

def save_params():
    """只能在 idle 时调用。"""
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
    """改参数。"""
    if name not in P:
        print('unknown param:', name)
        return False
    v = float(value)
    lo, hi = LIMITS[name]
    if v < lo or v > hi:
        print('out of range: %s=%s (%s~%s)' % (name, v, lo, hi))
        return False
    P[name] = v
    apply_params()
    if save:
        save_params()
    return True

def showp():
    for k in sorted(P):
        print('%-20s = %s' % (k, P[k]))