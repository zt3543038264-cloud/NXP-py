# 管理 LCD 初始化及运行状态显示。
from machine import Pin
from display import LCD_Drv, LCD

import cfg

cs = Pin('B29', Pin.OUT, value=True)
cs.high()
cs.low()
rst = Pin('B31', Pin.OUT, value=True)
dc = Pin('B5', Pin.OUT, value=True)
blk = Pin('C21', Pin.OUT, value=True)

drv = LCD_Drv(SPI_INDEX=2, BAUDRATE=60_000_000,
              DC_PIN=dc, RST_PIN=rst, LCD_TYPE=LCD_Drv.LCD200_TYPE)
dev = LCD(drv)
dev.color(0xFFFF, 0x0000)
dev.mode(2)
dev.clear()
VER = '0812a'
_last = ['', '', '', '', '']

def _line(row, text):
    if _last[row] == text:
        return
    _last[row] = text
    dev.str16(0, row * 20, '%-26s' % text, 0xFFFF)

def show_idle(angle):
    _line(0, 'IDLE  KEY1=start')
    _line(1, 'ang %7.2f' % angle)
    _line(2, 'ANG %.0f  RATE %.1f' % (cfg.ANG_KP, cfg.RATE_KP))
    _line(3, 'mid %.2f' % cfg.MID_ANGLE)
    _line(4, '')

def show_run(angle, target, err, pwm, lost=0):
    _line(0, 'RUN  LOST %d' % lost if lost else 'RUN')
    _line(1, 'ang %7.2f' % angle)
    _line(2, 'tgt %7.2f' % target)
    _line(3, 'err %7.1f' % err)
    _line(4, 'pwm %7.0f' % pwm)

def show_exit(code, msg):
    _line(0, 'EXIT %d' % code)
    _line(1, msg)
    _line(2, '')
    _line(3, '')
    _line(4, '')

def test():
    dev.clear()
    dev.str24(0, 0, 'LCD OK', 0xFFFF)
    dev.str16(0, 40, 'pins and spi fine', 0xFFFF)
