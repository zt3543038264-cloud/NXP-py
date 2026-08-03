# cfg.py —— 参数与常量。不碰任何硬件，可以单独 import 测试。
import os

# ---- 硬件常量（实测得出，不要改） ----
GYRO_LSB = 16.384          # ±2000dps
RAD2DEG  = 57.2958
DT       = 0.005           # 直立环周期 (s)
K_FILTER = 0.98            # 互补滤波系数

PARAM_FILE = '/flash/pid.txt'

# 不写反斜杠转义，避免复制时被改坏（见下方 2026-08-03 的存盘 bug）。
NL = chr(10)
BS = chr(92)      # 反斜杠本人，修复旧的坏文件时要用

DEFAULTS = {
    'MID_ANGLE': -4.6,          # 机械零点 (deg)  2026-08-03 实测
    'BAL_KP': 200.0,            # 直立环 P
    'BAL_KD': 5.0,              # 直立环 D
    'SPD_KP': 0.0,              # 速度环 P
    'SPD_KI': 0.0,              # 速度环 I
    'TARGET_SPEED': 0.0,        # 目标速度（计数/20ms）
    'FIRST_ANGLE_OUT': 2.0,     # 起步固定前倾角 (deg)
    'ANGLE_OFFSET_LIMIT': 8.0,  # 速度环对目标角的最大修正
    'MIN_ANGLE': -8.0,          # 目标角下限
    'ANGLE_LIMIT': 40.0,        # 倒地保护角
    'DUTY_LIMIT': 8000.0,       # 占空比限幅
    'ENC_LIMIT': 1500.0,        # 飞车保护（2026-08-03 实测定：空转 duty1500 约 585/20ms）
    'GYRO_DEAD': 0.0,           # 陀螺死区 (LSB)
    'MOTOR_SIGN': 1.0,          # 整体极性
}

LIMITS = {
    'MID_ANGLE':          (-20.0, 20.0),
    'BAL_KP':             (0.0, 2000.0),
    'BAL_KD':             (0.0, 200.0),
    'SPD_KP':             (0.0, 50.0),
    'SPD_KI':             (0.0, 5.0),
    'TARGET_SPEED':       (-500.0, 500.0),
    'FIRST_ANGLE_OUT':    (0.0, 15.0),
    'ANGLE_OFFSET_LIMIT': (0.0, 20.0),
    'MIN_ANGLE':          (-30.0, 0.0),
    'ANGLE_LIMIT':        (10.0, 60.0),
    'DUTY_LIMIT':         (0.0, 10000.0),
    'ENC_LIMIT':          (100.0, 20000.0),
    'GYRO_DEAD':          (0.0, 50.0),
    'MOTOR_SIGN':         (-1.0, 1.0),
}

EXIT_MSG = {1: 'fall down', 2: 'key stop', 3: 'encoder overspeed',
            4: 'remote stop'}

P = dict(DEFAULTS)

# 展开成模块属性，其他模块用 cfg.BAL_KP 读取
MID_ANGLE = BAL_KP = BAL_KD = SPD_KP = SPD_KI = 0.0
TARGET_SPEED = FIRST_ANGLE_OUT = ANGLE_OFFSET_LIMIT = MIN_ANGLE = 0.0
ANGLE_LIMIT = 40.0
DUTY_LIMIT = ENC_LIMIT = GYRO_DEAD = MOTOR_SIGN = 0


def clamp(v, lo, hi):
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


def apply_params():
    global MID_ANGLE, BAL_KP, BAL_KD, SPD_KP, SPD_KI
    global TARGET_SPEED, FIRST_ANGLE_OUT, ANGLE_OFFSET_LIMIT, MIN_ANGLE
    global ANGLE_LIMIT, DUTY_LIMIT, ENC_LIMIT, GYRO_DEAD, MOTOR_SIGN
    MID_ANGLE          = P['MID_ANGLE']
    BAL_KP             = P['BAL_KP']
    BAL_KD             = P['BAL_KD']
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


def load_params():
    try:
        f = open(PARAM_FILE, 'r')
    except OSError:
        print('no param file, using defaults.')
        apply_params()
        return
    with f:
        text = f.read()

    # 兼容旧的坏文件：把字面的反斜杠+n 也当换行。
    # 旧版 save_params() 把整个文件写成了一行，不补这句就永远读不回来。
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
    """只能在 idle 时调用。写 Flash 会阻塞几十毫秒。"""
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
    """改参数。save=False 时只改内存，不写 Flash。"""
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