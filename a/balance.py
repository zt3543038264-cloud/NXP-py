# balance.py —— 控制。回调只置标志，所有运算都在这里。
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

speed_i      = 0.0
speed_out    = 0.0
target_angle = 0.0
basic_pwm    = 0.0
angle_state  = 0


def run():
    """返回退出码。1=倒地 2=按键 3=编码器超限 4=远程停车"""
    global speed_i, speed_out, target_angle, basic_pwm, angle_state

    speed_i = 0.0
    speed_out = 0.0
    basic_pwm = 0.0
    angle_state = 0
    target_angle = cfg.MID_ANGLE
    enc.reset()
    tick.flag5 = False
    tick.flag20 = False

    start_ms = time.ticks_ms()
    exit_code = 0
    bt_div = 0

    while True:
        # ---- 5 ms：姿态 + 直立环 + 输出 ----
        if tick.flag5:
            tick.flag5 = False
            imu.update()

            if imu.fallen():
                exit_code = 1
                break

            if key.pressed(key.STOP):
                exit_code = 2
                break

            basic_pwm = (cfg.BAL_KP * (imu.angle - target_angle)
                         + cfg.BAL_KD * imu.rate)
            motor.drive(basic_pwm, basic_pwm)

        # ---- 20 ms：速度环 ----
        if tick.flag20:
            tick.flag20 = False
            enc.update()

            if enc.overspeed():
                exit_code = 3
                break

            elapsed = time.ticks_diff(time.ticks_ms(), start_ms)

            if angle_state == 0:
                # 起步前 500 ms 只直立，不管速度
                speed_out = 0.0
                if elapsed > 500:
                    angle_state = 1
            elif angle_state == 1:
                # 固定倾角加速，直到达到目标速度的一半
                speed_out = cfg.FIRST_ANGLE_OUT
                if abs(enc.speed) >= abs(cfg.TARGET_SPEED) * 0.5:
                    angle_state = 2
                    speed_i = 0.0      # 清积分，避免切换冲击
            else:
                e = enc.speed - cfg.TARGET_SPEED
                speed_i = cfg.clamp(speed_i + e, -5000.0, 5000.0)
                speed_out = cfg.clamp(cfg.SPD_KP * e + cfg.SPD_KI * speed_i,
                                      -cfg.ANGLE_OFFSET_LIMIT,
                                      cfg.ANGLE_OFFSET_LIMIT)

            # 车快于目标 → 需要后仰 → 目标角变小
            target_angle = cfg.MID_ANGLE - speed_out
            if target_angle < cfg.MIN_ANGLE:
                target_angle = cfg.MIN_ANGLE

            # 无线：50 Hz 收命令，10 Hz 回传遥测
            if bt.poll() == 'stop':
                exit_code = 4
                break
            bt_div += 1
            if bt_div >= 5:
                bt_div = 0
                bt.report(imu.angle, target_angle, enc.speed, basic_pwm)
                lcd.show_run(imu.angle, target_angle, enc.speed, basic_pwm)

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
                # idle 时也刷新倾角，第 3 步读机械零点靠它
                if tick.flag5:
                    tick.flag5 = False
                    imu.update()
                bt.poll(allow_save=True)     # 只有 idle 时允许写 Flash
                if time.ticks_diff(time.ticks_ms(), t0) > 500:
                    t0 = time.ticks_ms()
                    lcd.show_idle(imu.angle)
                    print('ang=%6.2f' % imu.angle)
                    bt.say('ang=%.2f\\n' % imu.angle)
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