#!/usr/bin/env bash
# 生成 5 秒级高密度 G 代码（600 段短 move），用于观察 serialqueue 流控
set -e
cd "$(dirname "$0")/../.."
{
  echo 'SET_KINEMATIC_POSITION X=0 Y=0 Z=0'
  echo 'G90'
  i=0
  while [ "$i" -lt 300 ]; do
    echo 'G1 X0.5 F9000'
    echo 'G1 X0 F9000'
    i=$((i + 1))
  done
  echo 'M400'
} > sim/lab/backpressure.gcode
wc -l sim/lab/backpressure.gcode
