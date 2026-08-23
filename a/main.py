import time
import key
import motor

motor.stop()
ESCAPE_MS = 3000
print('boot: hold KEY4 (or Ctrl+C) within 3 s to stay in REPL')
abort = False
try:
    for i in range(ESCAPE_MS // 10):
        key.dev.capture()
        if key.dev.get()[3]:
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
        run.main()
    except KeyboardInterrupt:
        pass
    finally:
        motor.stop()
        print('main exited.')
