
# PAW3395DM-T6QU MicroPython 驱动
# 适用于 RT1021-144P-BTB 核心板
# SPI Mode 3 (CPOL=1, CPHA=1), MSB first
#
# BTB 板 LPSPI4 引脚 (SPI id=3):
#   SCK  -> B18
#   MOSI -> B20
#   MISO -> B21
#   CS   -> B19

import time
from machine import SPI, Pin


class PAW3395:

    # ---- 常用寄存器地址 ----
    REG_PRODUCT_ID       = 0x00
    REG_REVISION_ID      = 0x01
    REG_MOTION           = 0x02
    REG_DELTA_X_L        = 0x03
    REG_DELTA_X_H        = 0x04
    REG_DELTA_Y_L        = 0x05
    REG_DELTA_Y_H        = 0x06
    REG_SQUAL            = 0x07
    REG_RAW_DATA_SUM     = 0x08
    REG_MAX_RAW_DATA     = 0x09
    REG_MIN_RAW_DATA     = 0x0A
    REG_SHUTTER_L        = 0x0B
    REG_SHUTTER_H        = 0x0C
    REG_MOTION_BURST     = 0x16   # 突发读取起始地址
    REG_POWER_UP_RESET   = 0x3A
    REG_SHUTDOWN         = 0x3B
    REG_RESOLUTION_X_L   = 0x40
    REG_RESOLUTION_X_H   = 0x41
    REG_RESOLUTION_Y_L   = 0x44
    REG_RESOLUTION_Y_H   = 0x45

    EXPECTED_PRODUCT_ID  = 0x51   # PAW3395DM-T6QU 产品 ID

    # ---- 初始化性能优化寄存器表 ----
    # 此表需要从 PAW3395 数据手册的 "Performance Optimization Registers" 章节获取
    # 格式: (寄存器地址, 写入值)
    # 示例占位符 — 请用数据手册中的真实值替换
    _PERF_OPT_REGS = [
        # (0xXX, 0xXX),
        # (0xXX, 0xXX),
        # ... 从数据手册中填入完整列表
    ]

    def __init__(self, spi_id=3, cs_pin='B19', nreset_pin=None, baudrate=2_000_000):
        """
        spi_id    : SPI 接口编号, B18/B20/B21 使用 3 (LPSPI4)
        cs_pin    : 片选引脚名称 (GPIO 软件控制)
        nreset_pin: 可选硬件复位引脚名称
        baudrate  : SPI 时钟频率, 最大 2 MHz
        """
        self._spi = SPI(spi_id)
        self._spi.init(baudrate=baudrate, polarity=1, phase=1)

        self._cs = Pin(cs_pin, Pin.OUT, value=1)

        self._nreset = None
        if nreset_pin is not None:
            self._nreset = Pin(nreset_pin, Pin.OUT, value=1)

        self._x_accum = 0
        self._y_accum = 0

    # ------------------------------------------------------------------
    #  底层 SPI 读写
    # ------------------------------------------------------------------

    def _write_reg(self, addr, data):
        """写单个寄存器: 地址 bit7=1 表示写操作"""
        self._cs.value(0)
        self._spi.write(bytearray([addr | 0x80, data & 0xFF]))
        self._cs.value(1)
        time.sleep_us(180)   # t_SRW: 两次写操作之间最小间隔

    def _read_reg(self, addr):
        """读单个寄存器: 地址 bit7=0 表示读操作"""
        self._cs.value(0)
        self._spi.write(bytearray([addr & 0x7F]))
        time.sleep_us(160)   # t_SRAD: 地址到数据的建立时间
        val = self._spi.read(1)[0]
        self._cs.value(1)
        time.sleep_us(20)
        return val

    def _burst_read(self, n_bytes):
        """突发读取 n_bytes 字节 (调用前需已发送突发地址)"""
        buf = bytearray(n_bytes)
        self._spi.readinto(buf)
        return buf

    def read_motion_burst_raw(self):
        """读取原始 Motion Burst 数据, 便于排查 SPI 通信问题"""
        self._cs.value(0)
        self._spi.write(bytearray([self.REG_MOTION_BURST & 0x7F]))
        time.sleep_us(35)   # t_SRAD_MOTBR

        buf = bytearray(12)
        self._spi.readinto(buf)
        self._cs.value(1)
        return buf

    # ------------------------------------------------------------------
    #  初始化
    # ------------------------------------------------------------------

    def init(self):
        """
        上电初始化序列.
        返回 True 表示成功, False 表示产品 ID 不符.
        """
        # 硬件复位 (如果有复位引脚)
        if self._nreset is not None:
            self._nreset.value(0)
            time.sleep_ms(10)
            self._nreset.value(1)
            time.sleep_ms(10)

        # CS 拉低再拉高以确保 SPI 接口复位
        self._cs.value(0)
        time.sleep_us(10)
        self._cs.value(1)
        time.sleep_us(10)

        # 上电复位
        self._write_reg(self.REG_POWER_UP_RESET, 0x5A)
        time.sleep_ms(50)

        # 读取并丢弃运动寄存器 (手册要求)
        for reg in [0x02, 0x03, 0x04, 0x05, 0x06]:
            self._read_reg(reg)

        # 写入性能优化寄存器 (如果已填入)
        for addr, val in self._PERF_OPT_REGS:
            self._write_reg(addr, val)
        if self._PERF_OPT_REGS:
            time.sleep_ms(10)

        # 验证产品 ID
        pid = self._read_reg(self.REG_PRODUCT_ID)
        return pid == self.EXPECTED_PRODUCT_ID

    # ------------------------------------------------------------------
    #  运动数据读取
    # ------------------------------------------------------------------

    def read_motion_burst(self):
        """
        突发读取运动数据 (推荐使用, 效率更高).
        返回 (dx, dy, motion_flag, squal)
          dx, dy      : 16 位有符号位移量 (单位: count)
          motion_flag : True 表示有新运动数据
          squal       : 表面质量 (0~255, 越大越好)
        """
        buf = self.read_motion_burst_raw()

        # 全 0xFF 通常表示 MISO 被上拉/悬空, CS 未选中, 或模块没有响应.
        # 全 0x00 通常表示 MISO 被下拉/短路, 或模块没有供电/没有输出.
        if buf == b'\xff' * 12 or buf == b'\x00' * 12:
            return 0, 0, False, buf[6]

        # buf[0]=Motion, buf[1]=Observation
        # buf[2]=dX_L, buf[3]=dX_H, buf[4]=dY_L, buf[5]=dY_H
        # buf[6]=SQUAL, buf[7]=Raw_Data_Sum, buf[8]=Max, buf[9]=Min
        # buf[10]=Shutter_L, buf[11]=Shutter_H
        motion_flag = bool(buf[0] & 0x80)

        dx = (buf[3] << 8) | buf[2]
        dy = (buf[5] << 8) | buf[4]

        # 转换为 16 位有符号整数
        if dx >= 0x8000:
            dx -= 0x10000
        if dy >= 0x8000:
            dy -= 0x10000

        squal = buf[6]
        return dx, dy, motion_flag, squal

    def read_motion(self):
        """
        逐寄存器读取运动数据 (备用方式).
        返回 (dx, dy, motion_flag)
        """
        motion = self._read_reg(self.REG_MOTION)
        motion_flag = bool(motion & 0x80)

        if not motion_flag:
            return 0, 0, False

        dx_l = self._read_reg(self.REG_DELTA_X_L)
        dx_h = self._read_reg(self.REG_DELTA_X_H)
        dy_l = self._read_reg(self.REG_DELTA_Y_L)
        dy_h = self._read_reg(self.REG_DELTA_Y_H)

        dx = (dx_h << 8) | dx_l
        dy = (dy_h << 8) | dy_l

        if dx >= 0x8000:
            dx -= 0x10000
        if dy >= 0x8000:
            dy -= 0x10000

        return dx, dy, True

    # ------------------------------------------------------------------
    #  累积位移 (可选)
    # ------------------------------------------------------------------

    def update_accum(self):
        """
        读取新数据并累加到内部计数器.
        返回 (x_accum, y_accum) 当前累积值.
        """
        dx, dy, flag, _ = self.read_motion_burst()
        if flag:
            self._x_accum += dx
            self._y_accum += dy
        return self._x_accum, self._y_accum

    def reset_accum(self):
        """清零累积计数器"""
        self._x_accum = 0
        self._y_accum = 0

    # ------------------------------------------------------------------
    #  分辨率设置
    # ------------------------------------------------------------------

    def set_resolution(self, cpi_x, cpi_y=None):
        """
        设置分辨率.
        cpi_x / cpi_y : CPI 值 (50~26000, 步进 50)
        若 cpi_y 不填则 X/Y 使用相同值.
        """
        if cpi_y is None:
            cpi_y = cpi_x

        # 寄存器值 = CPI / 50 - 1
        val_x = max(0, min(0x1FF, cpi_x // 50 - 1))
        val_y = max(0, min(0x1FF, cpi_y // 50 - 1))

        self._write_reg(self.REG_RESOLUTION_X_L,  val_x & 0xFF)
        self._write_reg(self.REG_RESOLUTION_X_H, (val_x >> 8) & 0x01)
        self._write_reg(self.REG_RESOLUTION_Y_L,  val_y & 0xFF)
        self._write_reg(self.REG_RESOLUTION_Y_H, (val_y >> 8) & 0x01)

    # ------------------------------------------------------------------
    #  调试信息
    # ------------------------------------------------------------------

    def read_product_id(self):
        """读取产品 ID"""
        return self._read_reg(self.REG_PRODUCT_ID)

    def read_revision_id(self):
        """读取版本 ID"""
        return self._read_reg(self.REG_REVISION_ID)

    def read_squal(self):
        """读取当前表面质量值"""
        return self._read_reg(self.REG_SQUAL)

    def read_shutter(self):
        """读取快门值 (反映光照强度)"""
        lo = self._read_reg(self.REG_SHUTTER_L)
        hi = self._read_reg(self.REG_SHUTTER_H)
        return (hi << 8) | lo