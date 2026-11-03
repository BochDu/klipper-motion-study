#!/usr/bin/env bash
# 构建 host simulator（仅首次）→ 批处理跑一遍 G 代码 → 解码下发指令
# 用法：bash scripts/run-sim.sh [gcode 文件]      （默认 sim/demo.gcode）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KLIPPER="$ROOT/klipper"
GCODE="${1:-$ROOT/sim/demo.gcode}"

if [ ! -f "$KLIPPER/out/klipper.dict" ]; then
    echo "==> 构建 MCU 端 host simulator"
    # /mnt/c 上的 CRLF 会让 shebang 失效，临时转 LF，构建结束后还原
    if grep -q $'\r' "$KLIPPER/scripts/check-gcc.sh" 2>/dev/null; then
        sed -i 's/\r$//' "$KLIPPER/scripts/check-gcc.sh"
        trap 'git -C "$KLIPPER" checkout -- scripts/check-gcc.sh 2>/dev/null || true' EXIT
    fi
    make -C "$KLIPPER" distclean >/dev/null 2>&1 || true
    cp "$KLIPPER/test/configs/hostsimulator.config" "$KLIPPER/.config"
    make -C "$KLIPPER" olddefconfig >/dev/null
    make -C "$KLIPPER" -j"$(nproc)"
fi

echo "==> 批处理运行 klippy"
python3 "$KLIPPER/klippy/klippy.py" "$ROOT/sim/host-sim.cfg" \
    -i "$GCODE" -o "$ROOT/sim/out-serial.log" \
    -d "$KLIPPER/out/klipper.dict" -l "$ROOT/sim/klippy.log"

echo "==> 解码 klippy 下发到 MCU 的指令（前 40 行）"
cd "$KLIPPER/klippy"
python3 parsedump.py ../out/klipper.dict "$ROOT/sim/out-serial.log" | sed -n '1,40p'
