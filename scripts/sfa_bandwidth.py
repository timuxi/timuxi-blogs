#!/usr/bin/env python3
"""TopK 稀疏 Attention（SFA）算子带宽估算脚本。

配套文章：《TopK 稀疏 Attention（SFA）算子带宽极限分析——950PR 与 950DT 实测对比》
https://timuxi.github.io/timuxi-blogs/article/sfa-bandwidth-analysis

按「数据量 ÷ 耗时」估算算子实际带宽：

    数据量 = gather 搬入 + gather 搬出 + MM1 左矩阵 + MM1 右矩阵 + FlashUpdate
    实际带宽 = 数据量 / 耗时

以目标 case（topk=2051 计算时按 2048 对齐、S1=4096、q_head_num=64、head_dim=512、
bf16）和 950PR 实测耗时 6.6 ms 为例，输出：

    总数据量 : 26,042,433,536 B = 24.25 GiB
    实际带宽 : 3.946 TB/s

与文章「1.2 硬件带宽基准」的数据量、以及「2. 现状（Baseline）」中 950PR 的
实际带宽一致。改动 `time_ms` 即可换算 950DT（实测 5.9 ms → 约 4.414 TB/s）。
"""

S1 = 4096
topk = 2048
head_dim = 512
q_headnum = 64
sizeof_half = 2
time_ms = 6.6

s1 = S1 * q_headnum
gather_in    = S1 * topk * head_dim * sizeof_half
gather_out   = S1 * topk * head_dim * sizeof_half
mm1_left     = S1 * head_dim * sizeof_half
mm1_right    = S1 * topk * head_dim * sizeof_half
flash_update = s1 * head_dim * sizeof_half

total = gather_in + gather_out + mm1_left + mm1_right + flash_update

time_s = time_ms / 1000.0
actual_bw = total / time_s

print(f"S1          : {S1:>15,}")
print(f"topk        : {topk:>15,}")
print(f"head_dim    : {head_dim:>15,}")
print(f"s1          : {s1:>15,}")
print(f"time        : {time_ms:.2f} ms")
print("-" * 50)
print(f"gather in   : {gather_in:>15,} B = {gather_in / 2**30:8.2f} GiB")
print(f"gather out  : {gather_out:>15,} B = {gather_out / 2**30:8.2f} GiB")
print(f"MM1 left    : {mm1_left:>15,} B = {mm1_left / 2**20:8.2f} MiB")
print(f"MM1 right   : {mm1_right:>15,} B = {mm1_right / 2**30:8.2f} GiB")
print(f"FlashUpdate : {flash_update:>15,} B = {flash_update / 2**20:8.2f} MiB")
print(f"TOTAL       : {total:>15,} B = {total / 2**30:8.2f} GiB")
print("-" * 50)
print(f"actual BW   : {actual_bw / 1e12:.3f} TB/s  ({actual_bw / 1e9:.2f} GB/s)")
