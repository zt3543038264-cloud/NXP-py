# run.py —— 入口。Alt+Q 跑这个文件，然后在 REPL 里输入 main()。
import cfg
import balance
import menu

main  = menu.main          # 屏幕菜单（推荐）
cli   = balance.main       # 不用屏幕时的老入口：REPL 打印 + KEY1 发车
setp  = cfg.setp
showp = cfg.showp


def reload():
    """改了纯逻辑模块后清缓存。改了硬件模块请直接 Ctrl+D 软复位。"""
    import sys
    for m in ('balance', 'bt', 'cfg'):
        if m in sys.modules:
            del sys.modules[m]
    print('cleared. re-run run.py (Alt+Q).')


print('main()    menu on screen')
print('cli()     no-screen fallback')
print('setp("BAL_KP", 260)   showp()   reload()')
print('probe:   key.test()  motor.test()  enc.test()  lcd.test()  bt.test()')