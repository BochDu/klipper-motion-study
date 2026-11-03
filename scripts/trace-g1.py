#!/usr/bin/env python3
"""1-1 实验：在 G1 通路上打点，打印调用栈 / Move 字段 / trapq_append 入参。

用法：
    python3 scripts/trace-g1.py [gcode 文件]        # 默认 sim/day1-g1.gcode

产物：sim/trace.log（klippy 原始日志 + TRACE 行）

原理：在 import klippy 之前对 toolhead / motion_queuing 的关键函数做猴子补丁。
      klipper/ 子模块保持干净，不改动一行源码；不需要真实 MCU。
"""
import os
import sys
import logging
import traceback
import importlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KLIPPER = os.path.join(ROOT, 'klipper')
KLIPPY = os.path.join(KLIPPER, 'klippy')
GCODE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'sim', 'day1-g1.gcode')
LOG = os.path.join(ROOT, 'sim', 'trace.log')
DICT = os.path.join(KLIPPER, 'out', 'klipper.dict')
OUT = os.path.join(ROOT, 'sim', 'out-serial.log')

sys.path.insert(0, KLIPPY)

import toolhead
mq = importlib.import_module('extras.motion_queuing')


def stack(depth=7):
    """只保留 klippy/ 内的调用帧，自底向上拼成 A <- B <- C"""
    frames = []
    for f in traceback.extract_stack()[:-1]:
        if '/klippy/' not in f.filename:
            continue
        short = f.filename.split('/klippy/')[-1]
        frames.append('%s:%d %s' % (short, f.lineno, f.name))
    return ' <- '.join(frames[-depth:])


# ---- 打点 1：G1 进入规划层的入口 ----------------------------------------
orig_move = toolhead.ToolHead.move


def move(self, newpos, speed):
    logging.info("TRACE ToolHead.move newpos=%s speed=%.4f", newpos, speed)
    logging.info("TRACE   stack: %s", stack())
    return orig_move(self, newpos, speed)


toolhead.ToolHead.move = move

# ---- 打点 2：Move 入队时的字段（梯形/JD 计算之前） ----------------------
orig_add_move = toolhead.LookAheadQueue.add_move


def add_move(self, move):
    logging.info("TRACE Move.new move_d=%.6f axes_d=%s axes_r=%s",
                 move.move_d, move.axes_d, move.axes_r)
    logging.info("TRACE       velocity=%.4f accel=%.1f jd=%.6f min_move_t=%.6f"
                 " delta_v2=%.3f",
                 move.max_cruise_v2 ** .5, move.accel, move.junction_deviation,
                 move.min_move_t, move.delta_v2)
    res = orig_add_move(self, move)
    logging.info("TRACE       queue_len=%d junction_flush=%.4f want_flush=%s",
                 len(self.queue), self.junction_flush, res)
    return res


toolhead.LookAheadQueue.add_move = add_move

# ---- 打点 3：JD 拐角 + 梯形速度确定之后 ----------------------------------
orig_set_junction = toolhead.Move.set_junction


def set_junction(self, start_v2, cruise_v2, end_v2):
    orig_set_junction(self, start_v2, cruise_v2, end_v2)
    logging.info("TRACE Move.set_junction start_v=%.4f cruise_v=%.4f end_v=%.4f",
                 self.start_v, self.cruise_v, self.end_v)
    logging.info("TRACE       accel_t=%.6f cruise_t=%.6f decel_t=%.6f"
                 " (total=%.6f)",
                 self.accel_t, self.cruise_t, self.decel_t,
                 self.accel_t + self.cruise_t + self.decel_t)


toolhead.Move.set_junction = set_junction

# ---- 打点 4：写入 trapq 的入参（规划层 → 插补层的边界） ------------------
orig_lookup_trapq_append = mq.PrinterMotionQueuing.lookup_trapq_append


def lookup_trapq_append(self):
    fn = orig_lookup_trapq_append(self)

    def wrapper(tq, print_time, accel_t, cruise_t, decel_t,
                sx, sy, sz, rx, ry, rz, start_v, cruise_v, accel):
        logging.info("TRACE trapq_append t=%.6f accel_t=%.6f cruise_t=%.6f"
                     " decel_t=%.6f", print_time, accel_t, cruise_t, decel_t)
        logging.info("TRACE       start=(%.4f,%.4f,%.4f) axes_r=(%.4f,%.4f,%.4f)"
                     " start_v=%.4f cruise_v=%.4f accel=%.1f",
                     sx, sy, sz, rx, ry, rz, start_v, cruise_v, accel)
        return fn(tq, print_time, accel_t, cruise_t, decel_t,
                  sx, sy, sz, rx, ry, rz, start_v, cruise_v, accel)

    return wrapper


mq.PrinterMotionQueuing.lookup_trapq_append = lookup_trapq_append

# ---- 打点 5：前瞻 flush 的时机 ------------------------------------------
orig_process_lookahead = toolhead.ToolHead._process_lookahead


def _process_lookahead(self, lazy=False):
    n = len(self.lookahead.queue)
    orig_process_lookahead(self, lazy=lazy)
    logging.info("TRACE _process_lookahead lazy=%s moves_before=%d"
                 " print_time=%.6f state=%r",
                 lazy, n, self.print_time, self.special_queuing_state)


toolhead.ToolHead._process_lookahead = _process_lookahead

# ---- 启动 klippy（批处理模式） ------------------------------------------
if os.path.exists(LOG):
    os.remove(LOG)  # klippy 的日志是追加打开，先清掉上一次的 TRACE
sys.argv = ['klippy.py', os.path.join(ROOT, 'sim', 'host-sim.cfg'),
            '-i', GCODE, '-o', OUT, '-d', DICT, '-l', LOG]
import klippy

print("==> 打点运行中... 日志写入 %s（TRACE 不打印到终端）"
      % os.path.relpath(LOG, ROOT), flush=True)
klippy.main()

n = 0
if os.path.exists(LOG):
    with open(LOG) as f:
        n = sum(1 for line in f if 'TRACE' in line)
print("==> 完成：%d 行 TRACE" % n)
print("==> 查看：grep TRACE %s" % os.path.relpath(LOG, ROOT))
