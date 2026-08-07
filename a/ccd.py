# 双线性 CCD：识别赛道中心、丢线、路口和斑马线。
import time

from seekfree import TSL1401

VER = '0807k'          # 改一次就往后挪一格，run.vers() 靠它对表

CH_NEAR = 0
CH_FAR  = 1

MIN_CONTRAST = 30      # hi - lo 下限
MIN_BRIGHT   = 50      # hi 下限：低于此值说明根本没看到白跑道

# ---- “视野里还有没有蓝边”的判据（2026-08-06 十字实测后新增） ----
DARK_LEVEL = 45        # 低于此亮度算“暗”。卡在赛道 20 与十字 70 之间
MIN_DARK_N = 3         # 采样后至少要有这么多个暗点，否则判为大开口
MIN_WIDTH    = 14      # 白区像素数下限（太窄 = 噪声光条）
MAX_WIDTH    = 100     # 上限。只用来判断这一帧的宽度值不值得记住。
EDGE_GUARD   = 3       # 边界落在最外侧 3 个像素以内，就当那条边已经出了视野

MID = 63.5             # 128 像素的几何中心

# ---- 帧类型（_solve 的第四个返回值） ----
K_OK    = 0            # 正常（双边或单边补线）
K_DARK  = 1            # 太暗：最亮点都到不了 MIN_BRIGHT = 真出界
K_OPEN  = 2            # 大开口：很亮但找不到两侧蓝边 = 十字 / 路口
K_NOISE = 3            # 白区太窄，当噪声丢弃

DEFAULT_W = (85, 53)
_track_w  = [85, 53]

# ---- 斑马线（起终点） ----
ZEBRA_LO      = 20     # 统计窗口左端，避开阵列边缘的暗角
ZEBRA_HI      = 108    # 统计窗口右端
ZEBRA_CROSS   = 6      # 窗口内跳变次数超过这个数就当斑马线
ZEBRA_HOLD_MS = 1000   # 同一条斑马线在这段时间内只能计一次

NEAR_OFFSET = 1.5
FAR_OFFSET  = 0.5

# ---- err 的量程（2026-08-06 实测，所有转向调参的基准） ----

dev = TSL1401(1)       # 唯一参数是采集分频，不是引脚
dev.set_resolution(TSL1401.RES_8BIT)

near = dev.get(CH_NEAR)
far  = dev.get(CH_FAR)

near_err = 0.0
far_err  = 0.0
near_ok  = False
far_ok   = False
near_w   = 0
far_w    = 0
near_kind = K_OK       # 本帧类型，见上面 K_* 常量
far_kind  = K_OK
near_hi   = 0          # 近端最亮点，标定出界阀值时看它

freeze_w = False

near_cross  = 0        # 近端窗口内的黑白跳变次数
zebra       = False    # 本帧是否看到斑马线
zebra_count = 0        # 累计压过几条斑马线（起点那条也算）
_zebra_armed = True    # 必须先离开当前这条，下一条才允许计数
_zebra_t = None

def _dark_n(d):
    """粗采样统计画面里有多少个明显暗的像素。"""
    n = 0
    for i in range(0, 128, 4):
        if d[i] < DARK_LEVEL:
            n += 1
    return n

def _expand(d, th, c):
    """从种子像素 c 向两侧撑到白区边界，返回 (左端, 右端)。"""
    l = c
    while l > 0 and d[l - 1] > th:
        l -= 1
    r = c
    while r < 127 and d[r + 1] > th:
        r += 1
    return l, r

def _solve(d, off, ch):
    """自适应阈值 + 边界扫描。"""
    lo = min(d)
    hi = max(d)
    if hi < MIN_BRIGHT:
        return (0.0, False, 0, K_DARK)
    if hi - lo < MIN_CONTRAST or _dark_n(d) < MIN_DARK_N:
        return (0.0, False, 0, K_OPEN)
    th = (lo + hi) // 2

    if d[64] > th:
        l, r = _expand(d, th, 64)
    else:
        cl = -1
        for i in range(63, -1, -1):
            if d[i] > th:
                cl = i
                break
        cr = -1
        for i in range(65, 128):
            if d[i] > th:
                cr = i
                break
        if cl < 0 and cr < 0:
            return (0.0, False, 0, K_DARK)
        if cr < 0:
            l, r = _expand(d, th, cl)
        elif cl < 0:
            l, r = _expand(d, th, cr)
        else:
            ll, lr = _expand(d, th, cl)
            rl, rr = _expand(d, th, cr)
            if (lr - ll) >= (rr - rl):
                l, r = ll, lr
            else:
                l, r = rl, rr

    w = r - l + 1
    if w < MIN_WIDTH:
        return (0.0, False, 0, K_NOISE)

    l_ok = l >= EDGE_GUARD
    r_ok = r <= 127 - EDGE_GUARD

    if l_ok and r_ok:
        if w <= MAX_WIDTH and not freeze_w:
            _track_w[ch] = w      # 只有两边都确认时的宽度才可信
        return ((l + r) * 0.5 - MID - off, True, w, K_OK)
    half = _track_w[ch] * 0.5
    if l_ok:
        return (l + half - MID - off, True, w, K_OK)
    if r_ok:
        return (r - half - MID - off, True, w, K_OK)
    return (0.0, False, w, K_OPEN)

def _cross(d):
    """窗口内黑白跳变次数。"""
    lo = min(d)
    hi = max(d)
    if hi < MIN_BRIGHT or hi - lo < MIN_CONTRAST:
        return 0
    th = (lo + hi) // 2
    n = 0
    prev = d[ZEBRA_LO] > th
    for i in range(ZEBRA_LO + 1, ZEBRA_HI):
        cur = d[i] > th
        if cur != prev:
            n += 1
            prev = cur
    return n

def update():
    """20 ms 调一次。"""
    global near_err, far_err, near_ok, far_ok, near_w, far_w
    global near_kind, far_kind, near_hi
    global near_cross, zebra, zebra_count, _zebra_armed, _zebra_t
    near_err, near_ok, near_w, near_kind = _solve(near, NEAR_OFFSET, 0)
    far_err,  far_ok,  far_w,  far_kind  = _solve(far,  FAR_OFFSET,  1)
    near_hi = max(near)      # 标定 K_DARK 阀值用，控制里不直接用

    if near_kind == K_OPEN:
        near_cross = 0
    else:
        near_cross = _cross(near)
    zebra = near_cross > ZEBRA_CROSS

    if zebra:
        near_ok = False

    if zebra:
        now = time.ticks_ms()
        if _zebra_armed and (_zebra_t is None or
                             time.ticks_diff(now, _zebra_t) > ZEBRA_HOLD_MS):
            zebra_count += 1
            _zebra_t = now
        _zebra_armed = False
    else:
        _zebra_armed = True

def reset():
    """每次发车前调一次。"""
    global zebra_count, zebra, near_cross, _zebra_armed, _zebra_t
    zebra_count = 0
    zebra = False
    near_cross = 0
    _zebra_armed = True
    _zebra_t = None

def test(n=40, ticker_on=False):
    """架空标定用。"""
    import time
    import tick
    if not ticker_on:
        tick.start()
    try:
        for i in range(n):
            time.sleep_ms(200)    # 先等一拍，保证 pit2 至少采过一次
            update()
            print('near', round(near_err, 1), near_ok, near_w,
                  'k', near_kind,
                  'zeb', near_cross, zebra, zebra_count,
                  'far', round(far_err, 1), far_ok, far_w, far_kind,
                  '| n', min(near), max(near), '| f', min(far), max(far))
    finally:
        if not ticker_on:
            tick.stop()