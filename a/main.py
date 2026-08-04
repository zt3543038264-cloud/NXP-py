# main.py —— 上电自启动。只做两件事：给一个逃生窗口，然后进菜单。
# 不需要脱机时删掉本文件即可，其余 11 个模块完全不受影响。
import time

import key
import motor

motor.stop()        # 上电第一件事，保证电机是停的

ESCAPE_MS = 3000
print('boot: hold KEY4 (or Ctrl+C) within 3 s to stay in REPL')

abort = False
try:
    for i in range(ESCAPE_MS // 10):
        key.dev.capture()          # 没有 ticker 在跑，必须自己 capture
        if key.dev.get()[3]:       # KEY4
            abort = True
            break
        time.sleep_ms(10)
except KeyboardInterrupt:
    abort = True

if abort:
    print('aborted by user. REPL is yours.')
else:
    key.clear()
    import run
    try:
        run.main()                 # = menu.main()，屏幕菜单
    except KeyboardInterrupt:
        pass
    finally:
        motor.stop()
        print('main exited.')