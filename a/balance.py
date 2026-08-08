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

VER = '0807u'

speed_i      = 0.0
speed_out    = 0.0
target_angle = 0.0
basic_pwm    = 0.0
angle_state  = 0
rate_target  = 0.0
rate_i       = 0.0
turn_pwm  = 0.0
yaw_lp    = 0.0
ccd_err   = 0.0
ccd_lost  = 0

def run():
    """返回退出码。"""
    global speed_i, speed_out, target_angle, basic_pwm, angle_state
    global rate_target, rate_i
    global turn_pwm, yaw_lp, ccd_err, ccd_lost

    speed_i = 0.0
    speed_out = 0.0
    basic_pwm = 0.0
    angle_state = 0
    rate_target = 0.0
    rate_i = 0.0
    turn_pwm = 0.0
    yaw_lp = 0.0
    ccd_err = 0.0
    ccd_lost = 0
    target_angle = cfg.MID_ANGLE
    ccd.reset()          # 清掉上一轮的斑马线计数，忘了这句下一轮一发车就停
    enc.reset()          # 不 reset 的话第一拍差分是上次停车到现在的累计值
    tick.flag5 = False
    tick.flag10 = False
    tick.flag20 = False

    start_ms = time.ticks_ms()
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
    boost_prev = False   # 用来识别冲坡刚结束的那一拍
    boost_done = False   # 达到速度后锁定退出，防止在时间窗内反复进入
    boost_out = 0.0      # 当前实际使用的负方向冲坡倾角，带斜坡变化
    boosting = False
    spd_target = 0.0     # 遥测显示的平滑目标速度
    spd_cmd = 0.0        # 真正送入 PI 的目标；直道慢升、入弯快降

    while True:
        # ---- 5 ms：姿态 + 串级直立环 + 输出 ----
        if tick.flag5:
            tick.flag5 = False
            imu.update()

            if imu.fallen():
                exit_code = 1
                break

            if key.pressed(key.STOP):
                exit_code = 2
                break

            rate_target = cfg.ANG_KP * (target_angle - imu.angle)
            rate_target = cfg.clamp(rate_target,
                                    -cfg.RATE_LIMIT, cfg.RATE_LIMIT)
            rate_err = imu.rate - rate_target
            rate_i = cfg.clamp(rate_i + rate_err * cfg.DT,
                               -cfg.RATE_I_LIMIT, cfg.RATE_I_LIMIT)
            basic_pwm = cfg.RATE_KP * rate_err + cfg.RATE_KI * rate_i
            # ---- 转向环：5 ms 跑，因为阻尼项 yaw_rate 每拍都是新的 ----
            yaw_lp += (imu.yaw_rate - yaw_lp) * cfg.YAW_HP
            yaw_d = imu.yaw_rate - yaw_lp

            turn_err = cfg.clamp(ccd_err, -30.0, 30.0)
            turn_pwm = -(cfg.TURN_KP * turn_err
                         + 0.8 * abs(turn_err) * turn_err
                         + cfg.TURN_KD * yaw_d)
            turn_pwm = cfg.clamp(turn_pwm, -cfg.TURN_LIMIT, cfg.TURN_LIMIT)
            motor.drive(basic_pwm - turn_pwm, basic_pwm + turn_pwm)

        # ---- 10 ms：CCD采集与循迹误差（100 Hz） ----
        # CCD独立提频；编码器、速度PI和所有帧数计数仍保持20 ms，
        # 因此0807k已经调好的速度量纲和停车时间都不会改变。
        if tick.flag10:
            tick.flag10 = False
            ccd.update()

            if ccd.near_kind == ccd.K_OPEN and not cross_too_long:
                ccd_err = 0.0
            elif ccd.near_ok:
                if ccd.far_ok:
                    ccd_err = ((ccd.near_err + cfg.FAR_WEIGHT * ccd.far_err)
                               / (1.0 + cfg.FAR_WEIGHT))
                else:
                    ccd_err = ccd.near_err
            else:
                # 原来每20 ms乘0.6；现在每10 ms乘0.78，
                # 两拍0.78^2约等于0.61，时间衰减速度保持不变。
                ccd_err *= 0.78

        # ---- 20 ms：编码器、速度PI与状态计数（50 Hz） ----
        if tick.flag20:
            tick.flag20 = False
            enc.update()        # 仍然只能20 ms更新一次，保持速度量纲

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

            # ---- 前瞻入弯刹车 ----
            # 长直道上ccd_err接近0，速度会一直涨到TARGET_SPEED；等近端
            # 看到90度弯时，按SPD_DEC_STEP降速已经来不及。这里用远端CCD先
            # 认出急弯，并允许更大的降速和刹车倾角步长。
            if cfg.CURVE_ERR > 0:
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
            if cfg.RAMP_FAR_W > 0:
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

            # ---- 开局定时冲坡 ----
            # 实测0807s中速度目标已经到14，但目标角被抬到12.5后正向PWM
            # 反而只有约1000，车速仍接近0。这里不再让速度PI产生冲坡角，
            # 而是直接把目标角向负方向压低，获得更大的正向PWM。
            boosting = (not boost_done
                        and cfg.START_BOOST_MS > 0
                        and elapsed >= cfg.START_HOLD_MS
                        and elapsed < (cfg.START_HOLD_MS
                                       + cfg.START_BOOST_MS))
            if (boosting and cfg.START_BOOST_SPEED > 0
                    and enc.speed >= cfg.START_BOOST_SPEED):
                boosting = False
                boost_done = True

            if boost_prev and not boosting:
                # 退出固定倾角后，从当前实速重新接管普通0807k速度PI。
                speed_i = 0.0
                speed_out = 0.0
                spd_cmd = cfg.clamp(enc.speed, 0.0, cfg.TARGET_SPEED)
            boost_prev = boosting

            # 冲坡倾角每20 ms最多增加0.15度；退出时也按同样速度收回，
            # 避免目标角在一拍内跳变2.5度。
            if boosting:
                boost_out += min(0.15, cfg.START_BOOST_ANGLE - boost_out)
            elif boost_out > 0.0:
                boost_out -= min(0.15, boost_out)

            # ---- 速度环（普通阶段完全保留0807k逻辑） ----
            if elapsed < cfg.START_HOLD_MS:
                spd_cmd = 0.0
                spd_target = 0.0
                speed_i = 0.0
                speed_out = 0.0
                boost_out = 0.0
            elif boosting:
                # 固定倾角冲坡期间暂停速度PI，防止错误方向的输出抵消扭矩。
                spd_cmd = cfg.START_BOOST_SPEED
                spd_target = cfg.START_BOOST_SPEED
                speed_i = 0.0
                speed_out = 0.0
            elif cfg.SPD_KP == 0.0 and cfg.SPD_KI == 0.0:
                # ---- 开环回退路径（速度环关闭） ----
                spd_cmd = 0.0
                spd_target = 0.0
                if ramp_t0 is not None:
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

                if ramp_t0 is not None:
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
                    # 刹车时必须更快地放掉直道积起来的积分，
                    # 否则目标倾角会被积分顶着，刹不下来。
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

                speed_raw = cfg.clamp(speed_raw,
                                      -cfg.ANGLE_OFFSET_LIMIT,
                                      cfg.ANGLE_OFFSET_LIMIT)

                brake_step = (cfg.CURVE_BRAKE_STEP if braking
                              else cfg.SPD_BRAKE_STEP)
                speed_step = cfg.clamp(speed_raw - speed_out,
                                       -brake_step,
                                       0.08)
                speed_out += speed_step

            # ---- 限速（2026-08-06 晚） ----
            if (not boosting
                    and ramp_t0 is None
                    and cfg.SPD_CAP > 0
                    and enc.speed > cfg.SPD_CAP):
                speed_out = cfg.SPD_BRAKE

            # 普通0807k仍为MID+speed_out；只有开局冲坡额外减去
            # boost_out。正数START_BOOST_ANGLE因此会降低目标角、增加正向PWM。
            target_angle = cfg.clamp(cfg.MID_ANGLE + speed_out - boost_out,
                                     cfg.MIN_ANGLE,
                                     cfg.MID_ANGLE + cfg.ANGLE_OFFSET_LIMIT)

            if bt.poll() == 'stop':
                exit_code = 4
                break
            bt_div += 1
            if bt_div >= 5:
                bt_div = 0
                bt.report(imu.angle, target_angle, ccd_err, basic_pwm,
                          ccd_lost)
                bt.say('spd %.1f/%.1f %d %d b%d c%d'
                       % (enc.speed, spd_target, enc.left, enc.right,
                          1 if boosting else 0,
                          1 if braking else 0)
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