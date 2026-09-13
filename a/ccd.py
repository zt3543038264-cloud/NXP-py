# 双线性 CCD：识别赛道中心、丢线、路口和斑马线。
import time
from seekfree import TSL1401

VER = '0812a'
CH_NEAR = 0
CH_FAR = 1
MIN_CONTRAST = 22
MIN_BRIGHT = 30
DARK_LEVEL = 28
MIN_DARK_N = 3
MIN_WIDTH = 14
MAX_WIDTH = 100
EDGE_GUARD = 3
MID = 63.5
K_OK = 0
K_DARK = 1
K_OPEN = 2
K_NOISE = 3
DEFAULT_W = (85, 53)
_track_w = [85, 53]
ZEBRA_LO = 20
ZEBRA_HI = 108
ZEBRA_CROSS = 6
ZEBRA_HOLD_MS = 1000
NEAR_OFFSET = 1.5
FAR_OFFSET = 0.5

dev = TSL1401(1)
dev.set_resolution(TSL1401.RES_8BIT)
near = dev.get(CH_NEAR)
far = dev.get(CH_FAR)
near_err = 0.0
far_err = 0.0
near_ok = False
far_ok = False
near_w = 0
far_w = 0
near_kind = K_OK
far_kind = K_OK
near_hi = 0
freeze_w = False
near_cross = 0
zebra = False
zebra_count = 0
_zebra_armed = True
_zebra_t = None

def _dark_n(d):
    n = 0
    for i in range(0, 128, 4):
        if d[i] < DARK_LEVEL:
            n += 1
    return n

def _expand(d, th, c):
    l = c
    while l > 0 and d[l - 1] > th:
        l -= 1
    r = c
    while r < 127 and d[r + 1] > th:
        r += 1
    return l, r

def _solve(d, off, ch):
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
            _track_w[ch] = w
        return ((l + r) * 0.5 - MID - off, True, w, K_OK)
    half = _track_w[ch] * 0.5
    opening = (ch == CH_NEAR and w > _track_w[ch] * 1.4)
    if l_ok:
        if opening:
            return (0.0, False, w, K_OPEN)
        return (l + half - MID - off, True, w, K_OK)
    if r_ok:
        if opening:
            return (0.0, False, w, K_OPEN)
        return (r - half - MID - off, True, w, K_OK)
    return (0.0, False, w, K_OPEN)

def _cross(d):
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
    global near_err, far_err, near_ok, far_ok, near_w, far_w
    global near_kind, far_kind, near_hi
    global near_cross, zebra, zebra_count, _zebra_armed, _zebra_t
    near_err, near_ok, near_w, near_kind = _solve(near, NEAR_OFFSET, 0)
    far_err, far_ok, far_w, far_kind = _solve(far, FAR_OFFSET, 1)
    near_hi = max(near)
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
    global zebra_count, zebra, near_cross, _zebra_armed, _zebra_t
    zebra_count = 0
    zebra = False
    near_cross = 0
    _zebra_armed = True
    _zebra_t = None

def test(n=40, ticker_on=False):
    import time
    import tick
    if not ticker_on:
        tick.start()
    try:
        for i in range(n):
            time.sleep_ms(200)
            update()
            print('near', round(near_err, 1), near_ok, near_w,
                  'k', near_kind, 'zeb', near_cross, zebra, zebra_count,
                  'far', round(far_err, 1), far_ok, far_w, far_kind,
                  '| n', min(near), max(near), '| f', min(far), max(far))
    finally:
        if not ticker_on:
            tick.stop()
