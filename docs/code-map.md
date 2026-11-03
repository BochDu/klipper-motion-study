# 源码路径地图（子模块 `0cee841`）

计划文档里的路径来自旧版 Klipper，本版本已重构。下表左边是**计划/资料里的旧路径**，右边是**本仓库实际可跳转的路径**。

## 链路总览

```
G1 (gcode)
  └─ klippy/extras/gcode_move.py        GCodeMove：解析、坐标系/偏移变换、转机器坐标
      └─ klippy/toolhead.py             ToolHead.move() → Move + LookAheadQueue（前瞻/JD/梯形）
          └─ klippy/kinematics/*.py     运动学：机器坐标 → 各轴位置
              └─ klippy/chelper/trapq.c 轨迹队列（多 move 拼统一打印时间轴）
                  └─ klippy/chelper/stepcompress.c   pos(t) → step 时间戳 + 压缩
                      └─ klippy/chelper/steppersync.c / serialqueue.c   打包、流控、绝对时钟戳
                          └─ src/sched.c + src/stepper.c   MCU 事件堆调度、按时序翻转 step 引脚
```

## 旧路径 → 实际路径

| 环节 | 旧路径（计划/文章） | 本仓库实际路径 |
| ---- | ---- | ---- |
| G1 解析 / 坐标变换 | `klippy/gcode_move.py` | `klippy/extras/gcode_move.py`（`class GCodeMove`） |
| Move 对象 / JD 拐角 | `klippy/toolhead.py`（Move） | `klippy/toolhead.py`（`class Move`，`calc_junction` / `set_junction`） |
| 前瞻与梯形规划 | `klippy/lookahead.py` | **已并入** `klippy/toolhead.py`（`class LookAheadQueue`，`add_move` / `flush`） |
| 轨迹队列（Python 侧） | `klippy/trapq.py` | **已移除**；`trapq` 由 `klippy/extras/motion_queuing.py`（`allocate_trapq`）创建，Python 侧只透传 `toolhead.get_trapq()` |
| 轨迹队列（C 侧） | `chelper/trapq.c` | `klippy/chelper/trapq.c` |
| 运动学逆解 | `klippy/kinematics/*.py` | 同名，`klippy/kinematics/*.py` + `klippy/chelper/kin_*.c` / `itersolve.c` |
| 插补 + 压缩 | `chelper/stepcompress.c` | `klippy/chelper/stepcompress.c` |
| stepcompress Python 封装 | `klippy/stepper.py` | `klippy/stepper.py`（`class MCU_stepper`，FFI 直调 `stepcompress_*`） |
| MCU 打包 / oid | `klippy/mcu.c`（实为 `mcu.py`） | `klippy/mcu.py` |
| 发送队列 / 流控 | `klippy/serialqueue.c` | `klippy/chelper/serialqueue.c`（`klippy/serialhdl.py` 持有句柄） |
| 时钟同步 | `klippy/clock_sync.c` / `clock_sync.py` | `klippy/clocksync.py`（`class ClockSync`，回归估漂移） |
| MCU 事件调度 | `src/sched.c` | `src/sched.c`（最小堆 `timer`，无 RTOS） |
| MCU 脉冲输出 | `src/stepgen.c` | **已更名** `src/stepper.c`（`command_queue_step` / `stepper_event`） |
| 分层总览文档 | `docs/Code_Overview.md` | `docs/Code_Overview.md`（仍在） |
| 运动学文档 | `docs/Motion_analysis.md` | **已删除**，改看 `docs/Kinematics.md`、`docs/Protocol.md`、`docs/Debugging.md` |

## 检查过的关键符号

| 符号 | 位置 |
| ---- | ---- |
| `class Move` | `klippy/toolhead.py:14` |
| `class LookAheadQueue` | `klippy/toolhead.py:120` |
| `class GCodeMove` | `klippy/extras/gcode_move.py:8` |
| `class PrinterMotionQueuing` | `klippy/extras/motion_queuing.py:23` |
| `class MCU_stepper` | `klippy/stepper.py:22` |
| `class ClockSync` | `klippy/clocksync.py:12` |
| `command_queue_step` | `src/stepper.c:259` |
| `stepper_event` | `src/stepper.c:210` |

> 行号随子模块版本固定而稳定；升级子模块后请重新核对。
