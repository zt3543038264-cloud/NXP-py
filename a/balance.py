# 平衡车主控制：执行直立、速度、循迹、转向和停车保护。
import gc
import time

import cfg
import imu
import enc
import key
import motor
import tick
import bt
import lcd
import ccd

VER = '0812a'

speed_i      = 0.0
speed_out    = 0.0
speed_ff     = 0.0
target_angle = 0.0
basic_pwm    = 0.0
rate_target  = 0.0
rate_pwm     = 0.0       # 增量式角速度 PI 的内部输出状态
rate_err_prev = 0.0      # 上一拍角速度误差
turn_pwm  = 0.0
yaw_lp    = 0.0
ccd_err   = 0.0
ccd_lost  = 0

def run(track=True):
    """返回退出码。track=False = 纯直立：原地站立，专门调角度/角速度环。"""
    global speed_i, speed_out, speed_ff, target_angle, basic_pwm
    global rate_target, rate_pwm, rate_err_prev
    global turn_pwm, yaw_lp, ccd_err, ccd_lost

    speed_i = 0.0
    speed_out = 0.0
    speed_ff = 0.0
    basic_pwm = 0.0
    rate_target = 0.0
    rate_pwm = 0.0
    rate_err_prev = 0.0
    turn_pwm = 0.0
    yaw_lp = 0.0
    ccd_err = 0.0
    ccd_lost = 0
    target_angle = cfg.MID_ANGLE
    ccd.reset()          # 清斑马线计数，否则下一轮一发车就误判终点
    enc.reset()          # 以当前累计值为基准，否则第一拍差分混入停车期间的量
    tick.flag5 = False
    tick.flag10 = False
    tick.flag20 = False

    start_ms = time.ticks_ms()
    print('run: track=%s' % track)
    exit_code = 0
    bt_div = 0
    zebra_t0 = None      # 认出终点的时刻，None = 还没认出
    dark_n = 0           # 连续多少帧画面发黑
    ramp_t0 = None       # 进坡道的时刻，None = 不在坡上
    ramp_n = 0           # 连续多少帧看到坡道特征
    cross_n = 0          # 连续多少个20 ms状态拍处于 K_OPEN
    cross_too_long = False
    curve_n = 0          # 刹车保持计数，防止弯中误差瞬时变小就松刹
    braking = False      # 本拍是否处于入弯刹车
    spd_target = 0.0     # 遥测显示的平滑目标速度
    spd_cmd = 0.0        # 真正送入 PI 的目标；直道慢升、入弯快降

    while True:
        # ---- 5 ms：姿态 + 串级直立环 + 输出 ----
        if tick.flag5:
            tick.flag5 = False
            imu.update()
            key.dev.capture()

            if imu.fallen():
                exit_code = 1
                break

            if key.pressed(key.STOP):
                exit_code = 2
                break

            # Angle-loop PD: D term adds pitch-rate damping to the rate target.
            rate_target = (cfg.ANG_KP * (target_angle - imu.angle)
                           - cfg.ANG_KD * imu.rate)
            rate_target = cfg.clamp(rate_target,
                                    -cfg.RATE_LIMIT, cfg.RATE_LIMIT)
            rate_err = imu.rate - rate_target
            # 标准离散增量式 PI。RATE_KI 是已包含 5 ms 采样周期的
            # 离散积分系数，因此这里不再额外乘 DT。
            delta_pwm = (cfg.RATE_KP * (rate_err - rate_err_prev)
                         + cfg.RATE_KI * rate_err)
            rate_err_prev = rate_err

            # 限制控制器内部输出状态，避免误差长期累积成单向 PWM。
            # 误差反向后 delta_pwm 可立即把状态从限幅边界拉回来。
            rate_pwm = cfg.clamp(rate_pwm + delta_pwm,
                                 -cfg.RATE_OUT_LIMIT,
                                 cfg.RATE_OUT_LIMIT)

            # 速度前馈是瞬时项，单独叠加，不能积入增量式 PI 状态。
            basic_pwm = cfg.clamp(rate_pwm + speed_ff,
                                  -cfg.DUTY_LIMIT, cfg.DUTY_LIMIT)
            # ---- 转向环：5 ms 跑，因为阻尼项 yaw_rate 每拍都是新的 ----
            yaw_lp += (imu.yaw_rate - yaw_lp) * cfg.YAW_HP
            yaw_d = imu.yaw_rate - yaw_lp

            if track:
                turn_err = cfg.clamp(ccd_err, -30.0, 30.0)
                turn_pwm = -(cfg.TURN_KP * turn_err
                             + 0.8 * abs(turn_err) * turn_err
                             + cfg.TURN_KD * yaw_d)
                turn_pwm = cfg.clamp(turn_pwm, -cfg.TURN_LIMIT,
                                     cfg.TURN_LIMIT)
            else:
                turn_pwm = 0.0
            motor.drive(basic_pwm - turn_pwm, basic_pwm + turn_pwm)

        # ---- 10 ms：CCD 与循迹误差 ----
        # 编码器、速度 PI 和帧数计数仍在 20 ms 拍，速度量纲不变。
        if tick.flag10:
            tick.flag10 = False
            # 纯直立模式不读 CCD，循迹偏差恒为 0
            if track:
                ccd.update()

                if ccd.near_kind == ccd.K_OPEN and not cross_too_long:
                    # 十字内冻结衰减而不是清零：保持进十字前的修正
                    # 方向，让偏中心进十字的车在十字里继续向线靠；
                    # 清零则横向偏移无人纠正，出线后必然走弯
                    ccd_err *= 0.95
                elif ccd.near_ok:
                    if ccd.far_ok:
                        ccd_err = ((ccd.near_err
                                    + cfg.FAR_WEIGHT * ccd.far_err)
                                   / (1.0 + cfg.FAR_WEIGHT))
                    else:
                        ccd_err = ccd.near_err
                else:
                    # 丢线误差衰减：10 ms 乘 0.78，等效原来 20 ms 乘 0.6
                    ccd_err *= 0.78

        # ---- 20 ms：编码器、速度 PI 与状态计数 ----
        if tick.flag20:
            tick.flag20 = False
            enc.update()        # 只能 20 ms 更新一次，保持速度量纲

            if track:
                if ccd.near_kind == ccd.K_OPEN:
                    cross_n += 1
                else:
                    cross_n = 0
                cross_too_long = (cfg.CROSS_MAX_N > 0
                                  and cross_n > cfg.CROSS_MAX_N
                                  and ramp_t0 is None)
                if ccd.near_kind == ccd.K_OPEN and not cross_too_long:
                    ccd_lost = 0
                elif ccd.near_ok:
                    ccd_lost = 0
                else:
                    ccd_lost += 1
                    if ccd_lost > cfg.CCD_LOST_MAX:
                        ccd_err = 0.0

                if ccd.near_kind == ccd.K_DARK:
                    dark_n += 1
                else:
                    dark_n = 0
            else:
                # 纯直立：CCD 状态计数保持 0，丢线/发黑停车不生效
                cross_n = 0
                ccd_lost = 0
                dark_n = 0

            # ---- 前瞻入弯刹车 ----
            # 直道上 ccd_err≈0，等近端看到 90 度弯再降速来不及；
            # 用远端 CCD 提前认弯，并允许更大的降速和刹车步长。
            if track and cfg.CURVE_ERR > 0:
                corner_ahead = False
                if abs(ccd_err) >= cfg.CURVE_ERR:
                    corner_ahead = True
                elif ccd.far_ok and abs(ccd.far_err) >= cfg.CURVE_ERR:
                    corner_ahead = True
                elif (ccd.near_ok
                      and (ccd.far_kind == ccd.K_DARK
                           or ccd.far_kind == ccd.K_NOISE)):
                    # 近端还在路上但远端已经看不到赛道，基本就是急弯。
                    # 不把K_OPEN算在内，那是十字而不是弯道。
                    corner_ahead = True

                if corner_ahead:
                    curve_n = cfg.CURVE_HOLD_N
                elif curve_n > 0:
                    curve_n -= 1
                braking = curve_n > 0
            else:
                curve_n = 0
                braking = False

            # ---- 坡道 ----
            if track and cfg.RAMP_FAR_W > 0:
                now_ms = time.ticks_ms()
                if ramp_t0 is None:
                    if ccd.far_kind == ccd.K_OK and ccd.far_w >= cfg.RAMP_FAR_W:
                        ramp_n += 1
                    else:
                        ramp_n = 0
                    if ramp_n >= cfg.RAMP_N:
                        ramp_t0 = now_ms
                elif time.ticks_diff(now_ms, ramp_t0) > cfg.RAMP_MS:
                    ramp_t0 = None
                    ramp_n = 0
            ccd.freeze_w = ramp_t0 is not None

            elapsed = time.ticks_diff(time.ticks_ms(), start_ms)

            if enc.overspeed():
                exit_code = 3
                break

            if ccd_lost > cfg.CCD_STOP_MAX and ramp_t0 is None:
                exit_code = 5
                break

            if dark_n >= cfg.DARK_STOP_N and ramp_t0 is None:
                exit_code = 7
                break

            if elapsed < cfg.ZEBRA_BLIND_MS or ramp_t0 is not None:
                ccd.zebra_count = 0
            elif zebra_t0 is None:
                if ccd.zebra_count >= cfg.ZEBRA_STOP_N:
                    zebra_t0 = time.ticks_ms()
            elif time.ticks_diff(time.ticks_ms(),
                                 zebra_t0) >= cfg.ZEBRA_STOP_DELAY_MS:
                exit_code = 6
                break

            # ---- 速度环 ----
            speed_ff = 0.0
            if elapsed < cfg.START_HOLD_MS:
                spd_cmd = 0.0
                spd_target = 0.0
                speed_i = 0.0
                speed_out = 0.0
            elif cfg.SPD_KP == 0.0 and cfg.SPD_KI == 0.0:
                # ---- 开环回退路径（速度环关闭） ----
                spd_cmd = 0.0
                spd_target = 0.0
                if not track:
                    speed_out = 0.0            # 纯直立：不前进
                elif ramp_t0 is not None:
                    speed_out = cfg.FIRST_ANGLE_OUT + cfg.RAMP_LEAN
                elif ccd_lost >= 3:
                    speed_out = cfg.MIN_LEAN
                else:
                    speed_out = (cfg.FIRST_ANGLE_OUT
                                 - cfg.TURN_SLOW * abs(ccd_err))
                    if speed_out < cfg.MIN_LEAN:
                        speed_out = cfg.MIN_LEAN
            else:
                # ---- 带目标斜坡、前瞻减速和抗饱和的 PI 速度环 ----
                curve_err = abs(ccd_err)
                if ccd.far_ok and abs(ccd.far_err) > curve_err:
                    curve_err = abs(ccd.far_err)

                if not track:
                    spd_req = 0.0              # 纯直立：原地站立，手推即扰动
                elif ramp_t0 is not None:
                    spd_req = cfg.TARGET_SPEED
                elif braking:
                    spd_req = cfg.CURVE_SPEED
                elif ccd_lost >= 3:
                    spd_req = cfg.MIN_SPEED
                else:
                    spd_req = cfg.TARGET_SPEED - cfg.SPD_SLOW * curve_err
                    if spd_req < cfg.MIN_SPEED:
                        spd_req = cfg.MIN_SPEED

                if spd_req > spd_cmd:
                    spd_cmd += min(0.15, spd_req - spd_cmd)
                else:
                    # 入弯时允许更大的目标速度下降步长。
                    dec_step = (cfg.CURVE_DEC_STEP if braking
                                else cfg.SPD_DEC_STEP)
                    spd_cmd -= min(dec_step, spd_cmd - spd_req)

                spd_target = spd_cmd
                spd_err_raw = spd_target - enc.speed

                if spd_err_raw > 0.5:
                    spd_err = spd_err_raw - 0.5
                elif spd_err_raw < -0.5:
                    spd_err = spd_err_raw + 0.5
                else:
                    spd_err = 0.0

                if ramp_t0 is None and speed_i > 0.0:
                    # 刹车/入弯时快速放掉直道积分，否则目标角被顶着刹不下来
                    if braking:
                        speed_i *= 0.75
                    elif curve_err > 8.0:
                        speed_i *= 0.90

                if spd_err < 0.0 and speed_i > 0.0:
                    i_step = cfg.clamp(spd_err * 3.0, -8.0, 0.0)
                else:
                    i_step = cfg.clamp(spd_err, -2.0, 2.0)

                i_next = cfg.clamp(speed_i + i_step,
                                   -cfg.SPD_I_LIMIT,
                                   cfg.SPD_I_LIMIT)
                p_out = cfg.SPD_KP * spd_err
                test_out = p_out + cfg.SPD_KI * i_next

                pushing_forward = (test_out > cfg.ANGLE_OFFSET_LIMIT
                                    and spd_err > 0.0)
                pushing_reverse = (test_out < -cfg.ANGLE_OFFSET_LIMIT
                                    and spd_err < 0.0)
                if not (pushing_forward or pushing_reverse):
                    speed_i = i_next

                speed_raw = p_out + cfg.SPD_KI * speed_i

                if ramp_t0 is not None:
                    speed_raw += cfg.RAMP_LEAN

                # 坡道时为 RAMP_LEAN 预留额外前倾余量；否则平路已饱和时
                # 叠加的坡道倾角会被普通 ANGLE_OFFSET_LIMIT 截掉。
                angle_limit = cfg.ANGLE_OFFSET_LIMIT
                if ramp_t0 is not None:
                    angle_limit += cfg.RAMP_LEAN
                speed_raw = cfg.clamp(speed_raw, -angle_limit, angle_limit)

                # Assist only after the body has reached its requested lean.
                if (track and cfg.SPD_FF_PWM > 0.0 and spd_err > 0.0
                        and abs(target_angle - imu.angle)
                            <= cfg.SPD_FF_ANGLE_ERR):
                    ff_scale = cfg.clamp(abs(spd_err) / cfg.SPD_FF_FULL_ERR,
                                         0.0, 1.0)
                    # Positive speed error requests positive lean, whose
                    # immediate motor PWM direction is negative in this loop.
                    speed_ff = -cfg.SPD_FF_PWM * ff_scale

                brake_step = (cfg.CURVE_BRAKE_STEP if braking
                              else cfg.SPD_BRAKE_STEP)
                # 循迹模式保持“慢升快刹”；纯直立扰动可能来自任意
                # 方向，倾角指令正反两个方向都要快。
                rise_step = 0.20 if track else brake_step
                speed_step = cfg.clamp(speed_raw - speed_out,
                                       -brake_step,
                                       rise_step)
                speed_out += speed_step

            # ---- 限速 ----
            if (ramp_t0 is None
                    and cfg.SPD_CAP > 0
                    and enc.speed > cfg.SPD_CAP):
                speed_out = cfg.SPD_BRAKE

            target_max = cfg.MID_ANGLE + cfg.ANGLE_OFFSET_LIMIT
            if ramp_t0 is not None:
                target_max += cfg.RAMP_LEAN
            target_angle = cfg.clamp(cfg.MID_ANGLE + speed_out,
                                     cfg.MIN_ANGLE, target_max)

            if bt.poll() == 'stop':
                exit_code = 4
                break
            bt_div += 1
            if bt_div >= 5:
                bt_div = 0
                bt.report(imu.angle, target_angle, ccd_err, basic_pwm,
                          ccd_lost)
                near_lo = min(ccd.near)
                near_dn = ccd._dark_n(ccd.near)

                bt.say('s%.1f/%.1f h%d l%d q%d n%d k%d f%d w%d/%d'
                    % (enc.speed, spd_target,
                        ccd.near_hi,
                        near_lo,
                        ccd.near_hi - near_lo,
                        near_dn,
                        ccd.near_kind,
                        ccd.far_kind,
                        ccd.near_w,
                        ccd.far_w)
                    + cfg.NL)
                lcd.show_run(imu.angle, target_angle, ccd_err, basic_pwm,
                             ccd_lost)

            gc.collect()

    motor.stop()
    return exit_code

def main():
    cfg.load_params()
    cfg.showp()
    print('calibrating, keep the car still ...')
    imu.calibrate()
    print('gy_bias = %.3f   angle0 = %.2f' % (imu.gy_bias, imu.angle))

    tick.start()
    try:
        while True:
            print('idle. press KEY1 to start.')
            t0 = time.ticks_ms()
            while not key.pressed(key.START):
                if tick.flag5:
                    tick.flag5 = False
                    imu.update()
                    key.dev.capture()
                bt.poll(allow_save=True)     # 只有 idle 时允许写 Flash
                if time.ticks_diff(time.ticks_ms(), t0) > 500:
                    t0 = time.ticks_ms()
                    lcd.show_idle(imu.angle)
                    print('ang=%6.2f' % imu.angle)
                    bt.say('ang=%.2f' % imu.angle + chr(10))
                time.sleep_ms(5)

            key.clear()
            time.sleep_ms(500)       # 防止松手瞬间被当成停车
            key.clear()

            print('running.')
            code = run()
            msg = cfg.EXIT_MSG.get(code, '?')
            lcd.show_exit(code, msg)
            print('exit: %d  %s' % (code, msg))
            key.clear()
            time.sleep_ms(500)
    except KeyboardInterrupt:
        pass
    finally:
        tick.stop()
        motor.stop()
        print('stopped.')
