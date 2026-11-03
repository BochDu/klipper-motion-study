# Klipper 运动控制全链路数据流（1-1 产出）

> 目标：把「G1 → 规划 → 插补 → 下发 → MCU 出脉冲」按**三层三种语言**一次画清。
> 全部结论均在本仓库 host simulator 上实测（子模块 `0cee841`，`CLOCK_FREQ=20MHz`）。
> 复现命令见文末第 7 节。

## 1. 一图流（分层 + 线程边界）

```
┌─ 上位机 klippy（Python，主线程 reactor）─ 规划层 ────────────────────────┐
│                                                                        │
│  G 代码文件/串口                                                        │
│      │  reactor 事件                                                    │
│      ▼                                                                 │
│  klippy/gcode.py                _process_data() → _process_commands()   │
│      │  查表分派到注册的 handler                                         │
│      ▼                                                                 │
│  klippy/extras/gcode_move.py    cmd_G1()：G90/G91/G92、F 换算、偏移      │
│      │  move_with_transform(last_position, speed)                       │
│      ▼                                                                 │
│  klippy/toolhead.py             ToolHead.move()                        │
│      ├─ Move()                  笛卡尔 move：move_d / axes_r / accel    │
│      ├─ kin.check_move()        运动学审核（越界/限速）                  │
│      ├─ LookAheadQueue.add_move()   → calc_junction()：JD 拐角速度      │
│      └─ _process_lookahead() → flush() → set_junction()：梯形三段       │
│                                                                        │
│  边界①：trapq_append(trapq, print_time, accel_t, cruise_t, decel_t,     │
│                     start_pos, axes_r, start_v, cruise_v, accel)        │
│         ▲ 传的是「笛卡尔空间 + 统一时间轴上的三段时长」，不是各轴轨迹      │
└───────────────────────────────┬────────────────────────────────────────┘
                                │ CFFI
┌─ klippy/chelper（C，每 stepper 一条后台线程）─ 插补层 ──────────────────┐
│  trapq.c          struct trapq：move 链表，提供 pos(t)（分段解析式）     │
│      │  motion_queuing._flush_handler() → steppersyncmgr_gen_steps()    │
│      ▼                                                                 │
│  steppersync.c    se_background_thread()：被唤醒后生成 step             │
│  itersolve.c      itersolve_gen_steps_range()：迭代求解「第 N 步的时刻」 │
│      │  位置公式来自 kin_*.c（kin_cartesian.c / kin_corexy.c ...）       │
│      ▼                                                                 │
│  stepcompress.c   stepcompress_append()：存 MCU 时钟域的绝对 step 时刻   │
│                   stepcompress_flush() → compress_bisect_add()          │
│                   把时刻序列压成 queue_step{interval, count, add}        │
└───────────────────────────────┬────────────────────────────────────────┘
                                │
┌─ 下发层（Python + C）──────────────────────────────────────────────────┐
│  klippy/mcu.py            oid 分配、命令编码（msgproto）                │
│  klippy/clocksync.py      时钟同步：MCU tick ↔ 主机秒 的线性回归         │
│  chelper/serialqueue.c    发送队列 + 流控背压（独立 IO 线程）            │
└───────────────────────────────┬────────────────────────────────────────┘
                                │ 串口 / USB / CAN（批处理模式写文件）
┌─ MCU（C，裸机事件堆）─ 执行层 ─────────────────────────────────────────┐
│  src/command.c            DECL_COMMAND 分派 → command_queue_step()      │
│  src/stepper.c            仅把 interval/count/add 挂进本 stepper 队列    │
│  src/sched.c              最小堆定时器：到点触发 stepper_event()         │
│                           do_step(); next += interval; interval += add; │
└────────────────────────────────────────────────────────────────────────┘
```

## 2. 三层职责速查

| 层 | 位置 | 语言/线程 | 关键符号 | 职责 |
| -- | ---- | ---- | ---- | ---- |
| G 代码解析 | `klippy/gcode.py`、`klippy/extras/gcode_move.py` | Python / reactor 主线程 | `_process_commands`、`cmd_G1` | 文本 → 内部调用；坐标系、F 单位换算 |
| 运动规划 | `klippy/toolhead.py` | Python / 主线程 | `Move`、`LookAheadQueue`、`ToolHead.move` | 前瞻、JD 拐角、梯形速度、维护 print_time |
| 运动学审核 | `klippy/kinematics/*.py` | Python | `check_move`、`set_position`、`calc_position` | 限速/限位/位置反查 |
| 轨迹队列 | `klippy/chelper/trapq.c` | C（FFI 调用） | `trapq_append`、`trapq_alloc` | 多 move 拼到统一打印时间轴，提供 pos(t) |
| 插补 | `klippy/chelper/itersolve.c` + `kin_*.c` | C / **每 stepper 一条线程** | `itersolve_gen_steps_range` | 迭代求「每一步的 MCU 时刻」 |
| 压缩 | `klippy/chelper/stepcompress.c` | C / 同上线程 | `stepcompress_append`、`compress_bisect_add` | step 时刻 → `queue_step(interval,count,add)` |
| 下发 | `klippy/mcu.py`、`chelper/serialqueue.c`、`clocksync.py` | Python + C IO 线程 | `oid`、`serialqueue`、回归时钟 | 编码、排队、背压、时钟换算 |
| MCU 调度 | `src/sched.c` | C（中断上下文） | `sched_add_timer`、`sched_timer_dispatch` | 事件堆定时器，**无 RTOS** |
| MCU 输出 | `src/stepper.c` | C（定时器中断） | `command_queue_step`、`stepper_event` | 按时间戳翻转 step 引脚 |

## 3. 实测：`G1 X50 F3000` 的调用栈

`sim/trace.log`（`scripts/trace-g1.py` 打点）：

```
TRACE ToolHead.move newpos=[50.0, 0.0, 0.0, 0.0] speed=50.0000
TRACE   stack: reactor.py:351 _dispatch_loop
             <- reactor.py:304 _dispatch_fd_events
             <- gcode.py:476 _process_data
             <- gcode.py:223 _process_commands
             <- extras/gcode_move.py:161 cmd_G1
```

栈自底向上就是一条完整通路：`reactor 事件 → gcode 分派 → cmd_G1 → ToolHead.move`。
注意 `cmd_G1` 调的是 `move_with_transform`，它在 `gcode_move.py:62` 的 `_handle_ready()` 里
被绑定到 `ToolHead.move`（无 G-Code 变换时），所以栈里看不到这一跳。

## 4. 实测：Move 字段与梯形验算

配置：`max_velocity=300`、`max_accel=3000`、`square_corner_velocity=5`（默认）。

入队时（`LookAheadQueue.add_move` 前）：

| 字段 | 实测值 | 由来 |
| ---- | ---- | ---- |
| `move_d` | 50.0 | `|end_pos - start_pos|`（XYZ 欧氏距离） |
| `axes_r` | `(1,0,0,0)` | 单位方向向量 = `axes_d / move_d` |
| `velocity` | 50.0 | `F3000 × speed_factor(1/60)` |
| `accel` | 3000.0 | `max_accel` |
| `junction_deviation` | 0.003452 | `scv²·(√2−1)/max_accel = 25×0.41421/3000` |
| `min_move_t` | 1.0 | `move_d / velocity` |
| `delta_v2` | 300000 | `2·move_d·accel`（单段内 v² 的最大变化量） |

单段起停（`set_junction` 后，起点终点都是静止）：

```
accel_d  = (cruise_v² − start_v²) / (2·accel) = 2500/6000 = 0.416667 mm
decel_d  = 0.416667 mm
cruise_d = 50 − 2×0.416667      = 49.166667 mm
accel_t  = accel_d / ((0+50)/2)  = 0.016667 s
cruise_t = cruise_d / 50         = 0.983333 s
decel_t  = 0.016667 s            → 合计 1.016667 s
```

写入 trapq 的入参（边界①的实证）：

```
trapq_append t=0.250000 accel_t=0.016667 cruise_t=0.983333 decel_t=0.016667
            start=(0,0,0) axes_r=(1,0,0) start_v=0 cruise_v=50 accel=3000
```

**14 个入参逐个点名**（`chelper/trapq.c:121`，与 `toolhead.py:284-289` 的调用一一对应）：

| # | 参数 | 含义 |
| -- | ---- | ---- |
| 1 | `tq` | 轨迹队列句柄 |
| 2 | `print_time` | 本 move 在统一打印时间轴上的起点（秒） |
| 3-5 | `accel_t / cruise_t / decel_t` | 梯形三段时长 |
| 6-8 | `start_pos_x/y/z` | XYZ 起点（笛卡尔，mm） |
| 9-11 | `axes_r_x/y/z` | 单位方向向量 |
| 12 | `start_v` | 起始速度（mm/s） |
| 13 | `cruise_v` | 巡航速度（mm/s） |
| 14 | `accel` | 加速度（mm/s²） |

**为什么传「三段时长」而不是点位序列**：

- 位置是时间的解析函数（匀加速 / 匀速 / 匀减速三段的一、二次式），trapq 里 `pos(t)` 随时可算，无需存采样点；
- 一次 `trapq_append` 最多往队列挂 3 个 `struct move`（`trapq.c:129-139` 按段拆分），**开销与步数无关**；
- 离散化（连续 `pos(t)` → 每个 stepper 的 step 时刻）推迟到插补线程由 `itersolve` 迭代求根，各轴共享同一条时间轴 ⇒ 天然同步，且采样精度与规划解耦。

`t=0.25` 即 `BUFFER_TIME_START`（`toolhead.py:196`）：首个 move 要比"当前 MCU 时刻"至少提前 0.25 s 下发。
`print_time` 随后推进到 `0.25 + 1.016667 = 1.266667`，与日志一致。

两段 move（`sim/demo.gcode`，90° 拐角）的实测，用来看清「统一时间轴」和拐角速度：

```
move1: start_v=0    cruise_v=50  end_v=5    t=0.250000  accel/cruise/decel_t=0.016667/0.983417/0.015000
move2: start_v=5    cruise_v=100 end_v=0    t=1.265083  accel/cruise/decel_t=0.031667/0.466708/0.033333
```

- 第二段 `t` 正好等于第一段的结束时刻：**trapq 里所有 move 首尾相接，共享一条打印时间轴**；
- 拐角处 `end_v == start_v == 5.0 mm/s`，正是 `square_corner_velocity` 的默认值（JD 细节见 1-4）。

### 4.1 从 trapq 到 `queue_step`：匀速段 `interval=5000` 的推导

配置 `rotation_distance=40`、`microsteps=16`，`full_steps_per_rotation=200`（`stepper.py:312`）：

```
steps_per_mm = full_steps × microsteps / rotation_distance = 200 × 16 / 40 = 80
F3000 → 50 mm/s  ⇒  50 × 80 = 4000 step/s
CLOCK_FREQ = 20 MHz  ⇒  interval = 20_000_000 / 4000 = 5000 tick/step
```

解码结果 `queue_step oid=2 interval=5000 count=917 add=0` 正是它。
`interval` 是相邻两步的 MCU 时钟 tick 数，`count` 是该批次步数，`add` 是 `interval` 的逐阶增量
（二阶近似加速度）：加速段 `add<0`（间隔递减）、减速段 `add>0`（间隔递增），
**匀速段速度恒定 ⇒ 间隔不变 ⇒ `add=0`**。

**改 `microsteps=32`**：`steps_per_mm = 200×32/40 = 160` ⇒ `50×160 = 8000 step/s`
⇒ `interval = 20e6/8000 = 2500 tick`（**减半**）；同时 50 mm 的步数从 4000 变 8000，
`queue_step count` 累计翻倍。

已用临时配置（`/tmp` 副本，不改工作区）实测验证：

```
queue_step oid=2 interval=2500 count=7868 add=0      # 匀速段由 5000 变 2500
```

复现：`cp sim/host-sim.cfg /tmp/host-sim-32.cfg && sed -i 's/microsteps: 16/microsteps: 32/g' /tmp/host-sim-32.cfg`，
再按第 7 节命令把配置换成该副本即可。

## 5. 层间边界（最需要记住的 4 条）

1. **边界① gcode → toolhead**：`cmd_G1` 只产出「目标位置 + 速度（mm/s）」，单位与坐标系的脏活都在这里做完。
2. **边界② toolhead → trapq**：传**笛卡尔空间 + 统一时间轴**的三段时长与方向向量，**不是**各轴的独立梯形、也不是点位序列。
3. **边界③ trapq → step 事件**：IK 位置公式（`chelper/kin_*.c` 的 `calc_position_cb`）以函数指针注册
   （`kinematics/cartesian.py:19 setup_itersolve('cartesian_stepper_alloc')`），
   `itersolve.c` 在插补线程里对它**迭代求根**，反求「第 N 步发生的时刻」；
   Python 侧不批量逆解，且求解的未知量是**时间**不是位置（详见 `Kinematics.md:145-153`）。
4. **边界④ 下发 → MCU**：`queue_step` 三元组 `interval/count/add` 就是"二阶"的 step 序列，
   MCU 只做 `next += interval; interval += add`，**不做任何插补**。

## 6. 与既有文档的出入（已核对）

| 说法 | 实际情况 |
| ---- | ---- |
| `docs/Code_Overview.md` 写 `kin_cart.c` | 本版本文件是 `klippy/chelper/kin_cartesian.c` |
| `docs/code-map.md` 旧版写「运动学逆解在插补前、在 `kinematics/*.py` 里」 | **已核实并修正**：Python 侧只做 `check_move`/`set_position`/`calc_position` + 注册；IK 公式实体在 `chelper/kin_*.c`，由 `itersolve.c` 求根时单点调用（依据 `Kinematics.md:145-153`） |
| `sim/klippy.log` 出现"一次 move 被 flush 切成多段" | 已在常量段看到 `count=917 + 3002` 的拆分，属下发/flush 粒度问题，2-2 回头解释 |

## 7. 复现

```bash
bash scripts/run-sim.sh                    # 端到端跑 sim/demo.gcode + 解码 queue_step
python3 scripts/trace-g1.py                # 单条 G1 的规划层打点，产物 sim/trace.log
python3 scripts/trace-g1.py sim/demo.gcode # 换成任意 G 代码
```

> **注意**：`trace-g1.py` 用 klippy 的 `-l` 把日志写进文件，**终端不会打印 TRACE**（正常现象），
> 运行结束只给一行提示。看打点用 `grep TRACE sim/trace.log`；
> 完整日志（含 klippy 启动信息）直接 `cat sim/trace.log`。同理 `run-sim.sh` 的解码结果在 `sim/out-serial.log`。

`trace-g1.py` 用猴子补丁在 `ToolHead.move` / `LookAheadQueue.add_move` / `Move.set_junction` /
`trapq_append` / `_process_lookahead` 上打点，**不修改 `klipper/` 子模块任何一行**。
