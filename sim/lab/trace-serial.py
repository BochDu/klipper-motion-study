#!/usr/bin/env python3
"""2-3 实验：观察 serialqueue 流控背压。

用法：
    python3 sim/lab/trace-serial.py [cfg] [gcode]
默认 sim/lab/backpressure.cfg + sim/lab/backpressure.gcode。

打点（源码零改动，全在 Python 侧）：
  SQ GEN    每次 steppersyncmgr_gen_steps（批量生成 step 并 send_batch），
            打印 flush_time 与当时的 serialqueue 统计
  SQ SEND   每条普通命令经 SerialReader.raw_send 时的 minclock/reqclock
产物：sim/lab/backpressure-serial.log（wire）、backpressure-klippy.log。
"""
import os
import sys
import logging

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
KLIPPER = os.path.join(ROOT, 'klipper')
sys.path.insert(0, os.path.join(KLIPPER, 'klippy'))

import chelper  # noqa: E402
import serialhdl  # noqa: E402
import extras.motion_queuing as motion_queuing  # noqa: E402

CFG = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'backpressure.cfg')
GCODE = (sys.argv[2] if len(sys.argv) > 2
         else os.path.join(HERE, 'backpressure.gcode'))
OUT = os.path.join(HERE, 'backpressure-serial.log')
LOG = os.path.join(HERE, 'backpressure-klippy.log')

_state = {'reader': None, 'gen_n': 0}


def stats_str():
    reader = _state['reader']
    if reader is None:
        return "reader=None"
    try:
        return reader.stats(reader.reactor.monotonic())
    except Exception as e:
        return "ERR %r" % (e,)


# ---- 打点 1：普通命令的入队参数 -------------------------------------------
_orig_raw_send = serialhdl.SerialReader.raw_send


def traced_raw_send(self, cmd, minclock, reqclock, cmd_queue):
    if _state['reader'] is None:
        _state['reader'] = self
    logging.info("SQ SEND len=%d minclock=%d reqclock=%d",
                 len(cmd), minclock, reqclock)
    return _orig_raw_send(self, cmd, minclock, reqclock, cmd_queue)


serialhdl.SerialReader.raw_send = traced_raw_send

# ---- 打点 2：每次批量生成/下发 step 时的队列水位 ---------------------------
_orig_mq_init = motion_queuing.PrinterMotionQueuing.__init__


def mq_init(self, config):
    _orig_mq_init(self, config)
    orig_gen = self.steppersyncmgr_gen_steps

    def traced_gen(ssm, flush_time, gen_time, clear_time):
        _state['gen_n'] += 1
        res = orig_gen(ssm, flush_time, gen_time, clear_time)
        logging.info("SQ GEN #%d flush_time=%.3f %s",
                     _state['gen_n'], flush_time, stats_str())
        return res

    self.steppersyncmgr_gen_steps = traced_gen


motion_queuing.PrinterMotionQueuing.__init__ = mq_init

for f in (LOG, OUT):
    if os.path.exists(f):
        os.remove(f)

sys.argv = ['klippy.py', CFG, '-i', GCODE, '-o', OUT, '-d',
            os.path.join(KLIPPER, 'out', 'klipper.dict'), '-l', LOG]
import klippy  # noqa: E402
klippy.main()
