import cfg
import balance
import menu

main = menu.main
cli = balance.main
setp = cfg.setp
showp = cfg.showp
SOFT = ('balance', 'menu', 'bt', 'cfg')
HARD = ('ccd', 'lcd', 'imu', 'enc', 'key', 'motor', 'tick')

def reload():
    import sys
    for m in SOFT:
        if m in sys.modules:
            del sys.modules[m]
    print('cleared:', ' '.join(SOFT))
    print('NOT cleared, need Ctrl+D:', ' '.join(HARD))
    print('re-run run.py (Alt+Q).')

VER = '0812a'
WATCH = ('cfg', 'bt', 'ccd', 'lcd', 'balance', 'menu', 'tick', 'run')

def vers():
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
print('setp("ANG_KP", 260)   showp()   reload()')
print('probe:   key.test()  motor.test()  enc.test()  lcd.test()  bt.test()')
vers()
