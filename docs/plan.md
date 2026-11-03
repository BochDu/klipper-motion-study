# Klipper 运动控制链路学习计划

> 自包含文档：在任意设备 clone 源码 + 跑模拟器即可开始，无需打印机/开发板。
> 节奏：**3 周 × 每周 5 天**，每天 1 小时（40min 读码打日志 + 20min 笔记）。
> 原则：**全链路各环节同等重要，全部掌握**。规划、插补、下发、时钟同步、MCU 调度执行、异常处理，一个不落。

## 一、背景（前因）

系统学习 Klipper 完整运动控制链路：**规划 → 插补 → 序列下发 → 执行器**。
Klipper 采用「上位机(Python)规划+插补生成 step 序列，MCU 按时序输出脉冲」分层架构。目标是完整吃透这条链路的每个环节，为自身运动控制方案设计打好基础。

## 二、目标

完整掌握 Klipper 全链路的数据流、数据结构与时序边界：能独立跑通模拟器、读懂每一层源码、定位丢步/抖动/提前减速问题，沉淀出可为自身设计直接采用的思路与需规避的坑。

## 三、考核节点（覆盖全链路精华，逐层验收）

> 通过标准 = 计划完整覆盖并掌握 Klipper 从规划到执行的**每一层**，无偏废。

| 阶段 | 考核内容 | 通过标准 |
| ---- | ---- | ---- |
| 第1周末 | 运动规划层 | 能独立画出 G1→move→前瞻(JD)→梯形速度→trapq 完整链图；讲清梯形公式与 JD 约束；模拟器改参数观察变化 |
| 第2周末 | 插补+下发层 | 讲清 stepcompress 如何把连续轨迹离散为 step 时间戳、如何压缩；讲清 serialqueue 打包、流控背压、oid 机制；打日志复现 step 事件 |
| 第3周末 | 时序执行+异常层 | 讲清 clock_sync 时钟同步、MCU sched 事件调度、stepgen 按时序出脉冲；复现短/零长 move、M112 急停场景 |
| 结业 | 端到端综合 | 完整讲解一条 G 指令：上位机规划→插补→下发→时钟同步→MCU 出脉冲全过程；产出①完整链路图 ②**全链路设计要点清单** ③一次独立端到端演示 |

## 四、环境准备

上游本版本已不再提供 `config/simulator.cfg`，改用 host simulator 编译 + 批处理运行方式，完整步骤与踩坑见 [environment.md](environment.md)。

```bash
git clone --recursive https://github.com/BochDu/klipper-motion-study.git   # 含 klipper 子模块
cd klipper && make distclean && cp test/configs/hostsimulator.config .config \
  && make olddefconfig && make -j"$(nproc)"                            # 产出 out/klipper.dict
python3 klippy/klippy.py ../sim/host-sim.cfg -i ../sim/demo.gcode \
  -o ../sim/out-serial.log -d out/klipper.dict -l ../sim/klippy.log    # 批处理跑 G 代码
```

工具：VSCode + ctags 源码跳转；笔记只记【数据结构 / 函数入口 / 坑点】。

## 五、每日学习计划（三周，每周五天）

### 第 1 周｜运动规划

| 天 | 主题 | 1h 内任务 | 产出 |
| ---- | ---- | ---- | ---- |
| 1-1 | 全链路全景 + G1 通路 | 读 Code_Overview.md；分层标记 Python/chelper/simulator；发 `G1 X50 F3000` 跟调用栈 | 数据流简图 |
| 1-2 | gcode_move 坐标+运动学逆解 | 读 Move 类、逆解入口；切 CoreXY 打印 move 参数 | Move 字段清单 |
| 1-3 | Lookahead 单段梯形速度 | 读单段梯形公式；打印 v0/ve/vmax/各段时长 | 速度公式验算 |
| 1-4 | Lookahead JD 拐角 | JD 约束、反向迭代修正；改 junction_deviation 看拐角速度 | JD 逻辑笔记 |
| 1-5 | trapq 轨迹队列 | trapq.py+chelper/trapq.c；多 move 拼统一时间轴 | trapq 职责总结 |

### 第 2 周｜插补 + 下发通信

| 天 | 主题 | 1h 内任务 | 产出 |
| ---- | ---- | ---- | ---- |
| 2-1 | stepcompress 插补采样 | pos(t)→step 时间戳；打印 step{time,pin,dir} | step 事件结构 |
| 2-2 | stepcompress 步事件压缩 | queue_step 批量压缩；对比压缩前后下发量 | 压缩收益总结 |
| 2-3 | serialqueue + 流控背压 | 队列满时上游阻塞逻辑；oid 机制 | 流控链路梳理 |
| 2-4 | clock_sync 时钟同步 | 漂移补偿；绝对时间戳非延时 | 时钟同步影响 |
| 2-5 | 异常链路 | 短/零长 move 丢弃；M112 急停清队列 | 故障风险清单 |

### 第 3 周｜MCU 时序执行 + 综合沉淀

| 天 | 主题 | 1h 内任务 | 产出 |
| ---- | ---- | ---- | ---- |
| 3-1 | MCU sched 调度器 | 最小堆事件调度；无 RTOS 轮询取最近事件 | 调度逻辑笔记 |
| 3-2 | MCU stepper 脉冲输出 | 按时间戳翻转引脚；确认 MCU 不做插补 | stepper 流程 |
| 3-3 | 端到端链路复盘 | 连续拐角 G 代码全链路打日志串联 | 最终链路图 |
| 3-4 | 设计要点梳理 | 提炼全链路各环节可直接采用的设计与需规避的坑 | 设计要点清单 |
| 3-5 | 模拟器端到端演示 | 独立跑通 G 指令→step 脉冲，逐环节讲解 | 演示复盘 |

## 六、研读文件索引（按本仓库子模块版本 `0cee841` 校正）

```
[规划层] klippy/extras/gcode_move.py   # GCodeMove：G1 解析、坐标变换入口
         klippy/toolhead.py            # Move / LookAheadQueue：前瞻、JD 拐角、梯形规划
         klippy/kinematics/*.py        # 各运动学逆解入口（cartesian/corexy/delta...）
[插补层] klippy/chelper/stepcompress.c # 插补采样 + step 事件压缩
         klippy/stepper.py             # stepcompress 的 Python 封装（MCU_stepper）
         klippy/chelper/trapq.c        # 轨迹队列实现（C 侧）
[下发层] klippy/mcu.py                 # MCU 对象、oid 分配、命令打包
         klippy/chelper/serialqueue.c  # 发送队列、流控背压
         klippy/chelper/steppersync.c  # 步进同步与 flush
         klippy/clocksync.py           # 时钟同步（漂移回归）
[执行层] src/sched.c                   # MCU 事件堆调度（无 RTOS）
         src/stepper.c                 # 按时序输出脉冲（queue_step/stepper_event）
```

文档：`docs/Code_Overview.md`、`docs/Kinematics.md`、`docs/Debugging.md`、`docs/Protocol.md`。

## 七、核心避坑

1. 插补在**上位机**，MCU 只按时序出脉冲（两层职责不同，都要掌握）
2. 运动学逆解在 gcode_move 之后的 kinematics 层（插补前）
3. step 时间全是**绝对时间戳**，时钟同步是精度根基
4. MCU sched 是**事件堆裸调度，非抢占 RTOS**
5. 原生仅梯形速度，S 曲线需补丁，本期不涉及
