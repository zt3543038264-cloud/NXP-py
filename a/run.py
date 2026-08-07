# 程序入口及模块重载、版本检查辅助函数。
import cfg
import balance
import menu

main  = menu.main          # 屏幕菜单（推荐）
cli   = balance.main       # 不用屏幕时的老入口：REPL 打印 + KEY1 发车
setp  = cfg.setp
showp = cfg.showp

SOFT = ('balance', 'menu', 'bt', 'cfg')

HARD = ('ccd', 'lcd', 'imu', 'enc', 'key', 'motor', 'tick')

def reload():
    """改了纯逻辑模块后清缓存。"""
    import sys
    for m in SOFT:
        if m in sys.modules:
            del sys.modules[m]
    print('cleared:', ' '.join(SOFT))
    print('NOT cleared, need Ctrl+D:', ' '.join(HARD))
    print('re-run run.py (Alt+Q).')

VER = '0807k'

WATCH = ('cfg', 'bt', 'ccd', 'lcd', 'balance', 'menu', 'run')

def vers():
    """打印各模块的 VER，对不上的标 STALE。"""
    import sys
    bad = 0
    for m in WATCH:
        mod = sys.modules.get(m)
        if mod is None:
            print('  %-8s -- not imported' % m)
            continue
        v = getattr(mod, 'VER', None)
        if v is None:
            print('  %-8s -- no VER (old file)' % m)
            bad += 1
        elif v != VER:
            print('  %-8s %s  <-- STALE' % (m, v))
            bad += 1
        else:
            print('  %-8s %s' % (m, v))
    if bad:
        print('!! %d stale module(s): re-upload, then Ctrl+D.' % bad)
    else:
        print('all modules %s' % VER)
    return bad

print('main()    menu on screen')
print('cli()     no-screen fallback')
print('setp("BAL_KP", 260)   showp()   reload()')
print('probe:   key.test()  motor.test()  enc.test()  lcd.test()  bt.test()')
vers()