import time
from machine import UART

u = UART(2)
u.init(9600, bits=8, parity=None, stop=1)
print('type on phone now')
for i in range(100):
    n = u.any()
    if n:
        print(n, u.read(n))
    time.sleep_ms(100)
print('done')