# 读取板载按键并提供按键测试。
from machine import Pin

_PINS = ('D13', 'D14', 'D15', 'D17')

class _GPIOKeys:
    def __init__(self):
        self._pins = tuple(Pin(name, Pin.IN, Pin.PULL_UP) for name in _PINS)
        self._last = [0, 0, 0, 0]
        self._state = [0, 0, 0, 0]
    def capture(self):
        for i, pin in enumerate(self._pins):
            value = 1 if pin.value() == 0 else 0
            if value == self._last[i]:
                self._state[i] = value
            self._last[i] = value
    def get(self):
        return self._state
    def clear(self, idx=None):
        pass

dev = _GPIOKeys()
START = 0
STOP = 1

def pressed(idx):
    return dev.get()[idx]

def clear(idx=None):
    if idx is None:
        dev.clear()
    else:
        dev.clear(idx)

def test():
    import time
    while True:
        dev.capture()
        print(dev.get())
        time.sleep_ms(200)
