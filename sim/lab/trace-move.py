#!/usr/bin/env python3
"""1-2 实验：打印 Move 字段（规划层输入），并在解析下发日志时对照各轴步数。

用法：
    python3 sim/lab/trace-move.py <cfg> <gcode> <名前缀>

产物：sim/lab/<名前缀>-serial.log、sim/lab/<名前缀>-klippy.log
原理：import klippy 之前对 toolhead.Move.__init__ 打点，源码零改动。
"""
import os
import sys
import logging

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
KLIPPER = os.path.join(ROOT, 'klipper')
KLIPPY = os.path.join(KLIPPER, 'klippy')
CFG, GCODE, NAME = sys.argv[1], sys.argv[2], sys.argv[3]
OUT = os.path.join(HERE, NAME + '-serial.log')
LOG = os.path.join(HERE, NAME + '-klippy.log')

sys.path.insert(0, KLIPPY)
import toolhead

orig_init = toolhead.Move.__init__


def init(self, th, start_pos, end_pos, speed):
    orig_init(self, th, start_pos, end_pos, speed)
    logging.info("KIN start=%s end=%s speed=%.4f move_d=%.6f axes_d=%s "
                 "axes_r=%s kinematic=%s min_move_t=%.6f delta_v2=%.3f",
                 self.start_pos, self.end_pos, speed, self.move_d,
                 self.axes_d, self.axes_r, self.is_kinematic_move,
                 self.min_move_t, self.delta_v2)


toolhead.Move.__init__ = init

sys.argv = ['klippy.py', CFG, '-i', GCODE, '-o', OUT, '-d',
            os.path.join(KLIPPER, 'out', 'klipper.dict'), '-l', LOG]
import klippy
klippy.main()
