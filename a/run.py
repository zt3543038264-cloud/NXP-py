# run.py —— 入口。Alt+Q 跑这个文件，然后在 REPL 里输入 main()。
import cfg
import balance

main  = balance.main
setp  = cfg.setp
showp = cfg.showp


def reload():
    """改了纯逻辑模块后清缓存。改了硬件模块请直接 Ctrl+D 软复位。"""
    import sys
    for m in ('balance', 'bt', 'cfg'):
        if m in sys.modules:
            del sys.modules[m]
    print('cleared. re-run run.py (Alt+Q).')


print('main()   setp("BAL_KP", 260)   showp()   reload()')
print('probe:   import key; key.test()   /   import motor; motor.test()')