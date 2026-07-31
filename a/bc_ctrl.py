# bc_ctrl.py —— 控制循环。回调只置标志，运算全在这里。
import gc
import time

import bc_cfg as cfg
import bc_hw as hw
import bc_att as att
import bc_comm as comm

speed        = 0.0
speed_i      = 0.0
speed_out    = 0.0
target_angle = 0.0
basic_pwm    = 0.0
angle_state  = 0


def run():
    """返回退出码。1=倒地 2=按键 3=编码器超限 4=远程停车"""
    global speed, speed_i, speed_out, target_angle, basic_pwm, angle_state

    speed = 0.0
    speed_i = 0.0
    speed_out = 0.0
    basic_pwm = 0.0
    angle_state = 0
    target_angle = cfg.MID_ANGLE
    hw.enc_l.get()
    hw.enc_r.get()
    hw.flag5 = False
    hw.flag20 = False

    start_ms = time.ticks_ms()
    exit_code = 0
    bt_div = 0

    while True:
        # ---- 5 ms：姿态 + 直立环 + 输出 ----
        if hw.flag5:
            hw.flag5 = False
            att.update()

            if abs(att.angle - cfg.MID_ANGLE) > cfg.ANGLE_LIMIT:
                exit_code = 1
                break

            if hw.key.get()[0]:
                exit_code = 2
                break

            basic_pwm = (cfg.BAL_KP * (att.angle - target_angle)
                         + cfg.BAL_KD * att.rate)
            hw.set_motor(basic_pwm, basic_pwm)

        # ---- 20 ms：速度环 ----
        if hw.flag20:
            hw.flag20 = False
            el = hw.enc_l.get()
            er = hw.enc_r.get()

            if abs(el) > cfg.ENC_LIMIT or abs(er) > cfg.ENC_LIMIT:
                exit_code = 3
                break

            speed = 0.7 * speed + 0.3 * ((el + er) * 0.5)
            elapsed = time.ticks_diff(time.ticks_ms(), start_ms)

            if angle_state == 0:
                # 起步前 500 ms 只直立，不管速度
                speed_out = 0.0
                if elapsed > 500:
                    angle_state = 1
            elif angle_state == 1:
                # 固定倾角加速，直到达到目标速度的一半
                speed_out = cfg.FIRST_ANGLE_OUT
                if abs(speed) >= abs(cfg.TARGET_SPEED) * 0.5:
                    angle_state = 2
                    speed_i = 0.0      # 清积分，避免切换冲击
            else:
                e = speed - cfg.TARGET_SPEED
                speed_i = hw.clamp(speed_i + e, -5000.0, 5000.0)
                speed_out = hw.clamp(cfg.SPD_KP * e + cfg.SPD_KI * speed_i,
                                     -cfg.ANGLE_OFFSET_LIMIT,
                                     cfg.ANGLE_OFFSET_LIMIT)

            # 车快于目标 → 需要后仰 → 目标角变小
            target_angle = cfg.MID_ANGLE - speed_out
            if target_angle < cfg.MIN_ANGLE:
                target_angle = cfg.MIN_ANGLE

            # 无线：50 Hz 收命令，10 Hz 回传遥测
            if comm.poll() == 'stop':
                exit_code = 4
                break
            bt_div += 1
            if bt_div >= 5:
                bt_div = 0
                comm.report(att.angle, target_angle, speed, basic_pwm)

            gc.collect()

    hw.stop_motor()
    return exit_code


def main():
    cfg.load_params()
    cfg.showp()
    print('calibrating, keep the car still ...')
    att.calibrate()
    print('gy_bias = %.3f   angle0 = %.2f' % (att.gy_bias, att.angle))

    hw.start_tickers()
    try:
        while True:
            print('idle. press KEY1 to start.')
            t0 = time.ticks_ms()
            while not hw.key.get()[0]:
                # idle 时也刷新倾角，第 3 步读机械零点靠它
                if hw.flag5:
                    hw.flag5 = False
                    att.update()
                comm.poll(allow_save=True)   # 只有 idle 时允许写 Flash
                if time.ticks_diff(time.ticks_ms(), t0) > 500:
                    t0 = time.ticks_ms()
                    print('ang=%6.2f' % att.angle)
                    comm.say('ang=%.2f\\n' % att.angle)
                time.sleep_ms(5)

            hw.key.clear()
            time.sleep_ms(500)       # 防止松手瞬间被当成停车
            hw.key.clear()

            print('running.')
            code = run()
            print('exit: %d  %s' % (code, cfg.EXIT_MSG.get(code, '?')))
            hw.key.clear()
            time.sleep_ms(500)
    except KeyboardInterrupt:
        pass
    finally:
        hw.stop_tickers()
        hw.stop_motor()
        print('stopped.')