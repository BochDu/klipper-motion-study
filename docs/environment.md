# 环境与可复现运行

目标：**不接打印机、不接开发板**，在 PC 上跑通「G 代码 → klippy 规划/插补 → 下发指令」并可直接解码观察。

本仓库子模块版本（`0cee841`）已不提供 `config/simulator.cfg`，改为 **编译 host simulator + 批处理模式** 运行：
MCU 端只用来产出协议字典 `out/klipper.dict`，klippy 通过 `-o` 把要下发的报文写进文件，不依赖任何串口。

## 1. 前置环境

在 **Ubuntu 原生系统**上运行（不支持 Windows 原生运行，pty / gcc 依赖；Windows 用户请装 WSL）。

```bash
sudo apt update && sudo apt install -y build-essential git python3 python3-pip python3-dev libffi-dev
python3 -m pip install --user -r klipper/scripts/klippy-requirements.txt
```

Ubuntu 版本与 Python 版本的关系（`klippy-requirements.txt` 钉死了 `Jinja2==2.11.3` / `markupsafe==1.1.1`）：

| 发行版 | 自带 Python | 状态 |
| ---- | ---- | ---- |
| 20.04 | 3.8 | ✅ 已验证（本文所有输出均来自此环境） |
| 22.04 | 3.10 | 预期可用；装不上 C 扩展时补 `python3-dev libffi-dev` |
| 24.04 | 3.12 | ⚠️ 钉死的 jinja2/markupsafe 无 cp312 wheel，需改用系统 `python3.11` 或手动升 `jinja2>=3.1`+`markupsafe>=2.1`（未验证） |

> 若 `python3 -m venv` 报 `ensurepip is not available`，安装 `python3-venv` 或直接用 `--user` 安装（本次采用后者，Python 3.8.10）。
> Ubuntu 24.04 的 pip 受 PEP 668 限制，需要 `--user --break-system-packages` 或 venv。

## 2. 编译 MCU 端（host simulator）

```bash
cd klipper
make distclean
cp test/configs/hostsimulator.config .config     # 内容只有 CONFIG_MACH_SIMU=y
make olddefconfig
make -j"$(nproc)"
```

产物：
- `out/klipper.dict` — 协议字典（klippy 必需，记录可用命令与 `CLOCK_FREQ=20000000`）
- `out/klipper.elf` — host simulator 本体（本次仅用于编译验证，批处理模式用不到）

`make olddefconfig` 不能省：只 `cp` 配置直接 `make` 会因配置项未展开而报
`Multiple definitions for command 'identify'`。

## 3. 批处理跑一遍 G 代码

```bash
python3 klipper/klippy/klippy.py sim/host-sim.cfg \
  -i sim/demo.gcode -o sim/out-serial.log \
  -d klipper/out/klipper.dict -l sim/klippy.log
```

含义：`-i` 从文件读 G 代码（不开 tty）、`-o` 把发往 MCU 的报文写到文件（不开串口）、`-d` 指定字典。

正常结果（`sim/klippy.log`）：

```
Loaded MCU 'mcu' 126 commands (0cee841 / ...)
MCU 'mcu' config: CLOCK_FREQ=20000000 ... STEPPER_STEP_BOTH_EDGE=1
Configured MCU 'mcu' (500 moves)
Exiting (print time 1.797s)
```

## 4. 解码下发指令（看 step 事件）

```bash
cd klipper/klippy
python3 parsedump.py ../out/klipper.dict ../../sim/out-serial.log
```

节选：

```
config_stepper oid=2 step_pin=1 dir_pin=2 invert_step=0 step_pulse_ticks=40
set_next_step_dir oid=2 dir=1
queue_step oid=2 interval=5040825 count=1 add=0        # 起步
queue_step oid=2 interval=7277 count=15 add=-148       # 加速段(interval 递减)
queue_step oid=2 interval=5000 count=917 add=0         # 匀速段
queue_step oid=2 interval=5028 count=16 add=112        # 减速段(interval 递增)
```

数值校验（`sim/host-sim.cfg`：`rotation_distance=40`、`microsteps=16`）：

- 80 steps/mm × 50 mm = **4000 步**，与 X 轴 `queue_step count` 累计值完全一致；
- `F3000` = 50 mm/s → 4000 step/s → 20 MHz / 4000 = **5000 tick/step**，即匀速段的 `interval=5000`。

## 5. 一键脚本

```bash
bash scripts/run-sim.sh            # 默认跑 sim/demo.gcode
bash scripts/run-sim.sh my.gcode   # 换成自己的 G 代码
```

## 6. 踩坑记录

| 现象 | 原因 | 处理 |
| ---- | ---- | ---- |
| `make: scripts/check-gcc.sh: Command not found` | Windows git 检出子模块时脚本变成 CRLF，shebang 失效 | 子模块内 `git config core.autocrlf false && git rm -r --cached . -q && git reset --hard`；脚本里也做了临时 `sed -i 's/\r$//'` |
| `Multiple definitions for command 'identify'` | 只复制配置未 `make olddefconfig` | 补 `make olddefconfig` 后重新构建 |
| `ModuleNotFoundError: No module named 'greenlet'` | klippy 依赖未装 | 按 `scripts/klippy-requirements.txt` 安装 |
| `Option 'serial' in section 'mcu' must be specified` | 本版本 `[mcu]` 即使批处理也要求 `serial` | 配置里写 `serial: /dev/ttyACM0`，批处理不会真的打开 |
| `Unknown pin` / 引脚名不可用 | host simulator 没有 `PA0` 这类命名枚举 | 直接用**数字引脚** `1/2/3...`（`config_stepper step_pin=1` 已验证） |

## 7. 待验证（第 2~3 周再做）

- 用 `socat` 造虚拟串口 + 直接运行 `out/klipper.elf`，观察 MCU 侧 `sched`/`stepper` 的真实事件时序；
- 用 `scripts/stepstats.py` 统计下发量与压缩比（2-2 用）。
