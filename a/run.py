# run.py —— 入口。Alt+Q 跑这个文件，然后在 REPL 里输入 main()。
import bc_cfg as cfg
import bc_ctrl as ctrl

main  = ctrl.main
setp  = cfg.setp
showp = cfg.showp


def reload():
    """改了纯逻辑模块后清缓存。改了 bc_hw.py 请直接 Ctrl+D 软复位。"""
    import sys
    for m in ('bc_ctrl', 'bc_comm', 'bc_att', 'bc_cfg'):
        if m in sys.modules:
            del sys.modules[m]
    print('cleared. re-run run.py (Alt+Q).')


print('main()   setp("BAL_KP", 260)   showp()   reload()')