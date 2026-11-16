#!/usr/bin/env python3
"""1-3 实验：把 LookAheadQueue.flush() 的两趟扫描摊开打印。

用法：
    python3 sim/lab/trace-lookahead.py [cfg] [gcode]
默认 sim/host-sim.cfg + sim/lab/lookahead.gcode。

打印三段：
  LA ADD   入队时（calc_junction 之后）的 v2 上限：max_start_v2 / max_cruise_v2 / delta_v2
  LA REV   逆向扫描逐行（按源码 :146-169 复刻）：reachable / start_v2 / cruise_v2 / peak
  LA FWD   正向扫描 set_junction 的实际入参与产出
源码零改动；产物写 sim/lab/lookahead-*.log。
"""
import os
import sys
import logging

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
KLIPPER = os.path.join(ROOT, 'klipper')
sys.path.insert(0, os.path.join(KLIPPER, 'klippy'))

import toolhead

CFG = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'sim', 'host-sim.cfg')
GCODE = (sys.argv[2] if len(sys.argv) > 2
         else os.path.join(HERE, 'lookahead.gcode'))
OUT = os.path.join(HERE, 'lookahead-serial.log')
LOG = os.path.join(HERE, 'lookahead-klippy.log')

# ---- 打点 1：入队时的上界 ------------------------------------------------
orig_add = toolhead.LookAheadQueue.add_move


def add_move(self, move):
    res = orig_add(self, move)
    logging.info("LA ADD i=%d move_d=%.3f max_start_v2=%.1f max_cruise_v2=%.1f "
                 "delta_v2=%.1f mcr_delta_v2=%.1f",
                 len(self.queue) - 1, move.move_d, move.max_start_v2,
                 move.max_cruise_v2, move.delta_v2, move.mcr_delta_v2)
    return res


toolhead.LookAheadQueue.add_move = add_move


# ---- 打点 2：逆向扫描复刻（对照源码 :146-169） ---------------------------
def dump_reverse(queue):
    rows = []
    next_start_v2 = next_mcr_start_v2 = peak_cruise_v2 = 0.
    pending = 0
    for i in range(len(queue) - 1, -1, -1):
        m = queue[i]
        reachable = next_start_v2 + m.delta_v2
        start_v2 = min(m.max_start_v2, reachable)
        cruise_v2 = None
        pending += 1
        reach_mcr = next_mcr_start_v2 + m.mcr_delta_v2
        mcr_start_v2 = min(m.max_mcr_start_v2, reach_mcr)
        if mcr_start_v2 < reach_mcr:
            if (mcr_start_v2 + m.mcr_delta_v2 > next_mcr_start_v2
                    or pending > 1):
                peak_cruise_v2 = (mcr_start_v2 + reach_mcr) * .5
            cruise_v2 = min((start_v2 + reachable) * .5,
                            m.max_cruise_v2, peak_cruise_v2)
            pending = 0
        rows.append((i, m.move_d, reachable, start_v2, cruise_v2,
                     peak_cruise_v2))
        next_start_v2 = start_v2
        next_mcr_start_v2 = mcr_start_v2
    for r in reversed(rows):
        logging.info("LA REV i=%d move_d=%.3f reachable=%.1f start_v2=%.1f "
                     "cruise_v2=%s peak=%.1f",
                     r[0], r[1], r[2], r[3],
                     "None" if r[4] is None else "%.1f" % r[4], r[5])


orig_flush = toolhead.LookAheadQueue.flush


def flush(self, lazy=False):
    logging.info("LA FLUSH lazy=%s queued=%d", lazy, len(self.queue))
    dump_reverse(self.queue)
    return orig_flush(self, lazy=lazy)


toolhead.LookAheadQueue.flush = flush

# ---- 打点 3：正向扫描的最终入参 -----------------------------------------
orig_sj = toolhead.Move.set_junction


def set_junction(self, start_v2, cruise_v2, end_v2):
    orig_sj(self, start_v2, cruise_v2, end_v2)
    logging.info("LA FWD move_d=%.3f in(start_v2=%.1f cruise_v2=%.1f "
                 "end_v2=%.1f) out(start_v=%.4f cruise_v=%.4f end_v=%.4f "
                 "accel_t=%.6f cruise_t=%.6f decel_t=%.6f)",
                 self.move_d, start_v2, cruise_v2, end_v2,
                 self.start_v, self.cruise_v, self.end_v,
                 self.accel_t, self.cruise_t, self.decel_t)


toolhead.Move.set_junction = set_junction

for f in (LOG, OUT):
    if os.path.exists(f):
        os.remove(f)

sys.argv = ['klippy.py', CFG, '-i', GCODE, '-o', OUT, '-d',
            os.path.join(KLIPPER, 'out', 'klipper.dict'), '-l', LOG]
import klippy
klippy.main()
