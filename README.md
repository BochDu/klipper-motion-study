# klipper-motion-study

Klipper 运动控制链路（**规划 → 插补 → 序列下发 → MCU 时序执行**）源码学习仓库。

上游源码以 git submodule 固定在 `klipper/`，本仓库只存放：学习计划、每日记录、路径地图、可复现的实验环境。
在任意设备 `git clone --recursive` 后即可按 [docs/environment.md](docs/environment.md) 复现，无需打印机与开发板。

## 文档索引

| 文档 | 内容 |
| ---- | ---- |
| [docs/plan.md](docs/plan.md) | 初衷、目标、考核节点、三周每日计划 |
| [docs/environment.md](docs/environment.md) | 环境搭建、host simulator 构建、批处理跑通 G1、踩坑记录 |
| [docs/code-map.md](docs/code-map.md) | 计划里的旧路径 → 本仓库版本的**实际**路径对照 |
| [docs/dataflow.md](docs/dataflow.md) | 全链路数据流图（1-1 产出）：三层职责、G1 实测调用栈、层间边界 |
| [notes/README.md](notes/README.md) | 每日记录约定（六段式 + **自测规范**）与索引 |

## 目录结构

```
klipper-motion-study/
├── klipper/            # submodule：Klipper 上游源码（版本锚点见下）
├── docs/               # 计划、环境、源码地图
├── notes/              # 按日期记录：YYYY-MM-DD.md
├── sim/                # 可复现的模拟器配置与演示 G 代码（运行产物不入库）
├── scripts/run-sim.sh  # 一键构建 host simulator + 批处理跑一遍 + 解码下发指令
└── scripts/trace-g1.py # 规划层打点：打印 G1 调用栈、Move 字段、trapq_append 入参
```

## 快速开始

运行环境：Linux（Ubuntu / WSL），需要 `make`、`gcc`、`python3`。不接打印机、不接开发板。

```bash
sudo apt update
```

```bash
sudo apt install -y build-essential python3 python3-pip python3-dev libffi-dev
```

拉取 Klipper 子模块：

```bash
git submodule update --init --recursive
```

安装 Python 依赖：

```bash
python3 -m pip install -r klipper/scripts/klippy-requirements.txt
```

构建 host simulator，批处理跑 `sim/demo.gcode`，并解码下发指令：

```bash
bash scripts/run-sim.sh
```

## 版本锚点

- Klipper submodule：`0cee841`（`master`，2026-10-21，*z_thermal_adjust: Validate stepper_z kinematics lookup*）
- 子模块为浅克隆（`.gitmodules` 中 `shallow = true`）；需要完整历史时执行 `git -C klipper fetch --unshallow`

> 上游对该版本做过结构性重构：`lookahead.py` / `trapq.py` 已并入 `klippy/toolhead.py`，
> `gcode_move.py` 移入 `klippy/extras/`，`chelper/` 移入 `klippy/chelper/`，MCU 端 `stepgen.c` 更名为 `stepper.c`。
> 计划中出现的旧文件名请对照 [docs/code-map.md](docs/code-map.md)。

## 学习进度

| 天 | 主题 | 状态 | 记录 |
| -- | ---- | ---- | ---- |
| 1-1 | 全链路全景 + G1 通路 | 已完成 | [2026-11-02](notes/2026-11-02.md)（环境）、[2026-11-03](notes/2026-11-03.md)（调用栈与数据流图） |
| 1-2 | gcode_move 坐标 + 运动学逆解 | 未开始 | - |
| 1-3 | Lookahead 单段梯形速度 | 未开始 | - |
| 1-4 | Lookahead JD 拐角 | 未开始 | - |
| 1-5 | trapq 轨迹队列 | 未开始 | - |
| 2-1 | stepcompress 插补采样 | 未开始 | - |
| 2-2 | stepcompress 步事件压缩 | 未开始 | - |
| 2-3 | serialqueue + 流控背压 | 未开始 | - |
| 2-4 | clock_sync 时钟同步 | 未开始 | - |
| 2-5 | 异常链路（短/零长 move、M112） | 未开始 | - |
| 3-1 | MCU sched 调度器 | 未开始 | - |
| 3-2 | MCU stepper 脉冲输出 | 未开始 | - |
| 3-3 | 端到端链路复盘 | 未开始 | - |
| 3-4 | 设计要点梳理 | 未开始 | - |
| 3-5 | 模拟器端到端演示 | 未开始 | - |
