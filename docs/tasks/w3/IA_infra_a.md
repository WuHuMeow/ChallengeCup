# 仿真基础设施 A（IA） W3 任务书

> 周期：8/3（周日）- 8/9（周六） | 核心目标：保障全量实验运行环境稳定，处理运行中的技术问题，并启动 Docker 环境搭建

## 本周背景

本周进入 360 组（20 路口 × 3 算法 × 6 种子）原始流量实验阶段。0.1s 步长路口（11-13、15-20）实际计算量是 1s 路口的 ~10 倍，需重点监控。同时启动 W4 Docker 打包的前置工作：基于 W2 调研结论编写 Dockerfile 初稿（基础镜像 `ubuntu:22.04`，apt 安装 SUMO + Python 依赖）。

## 每日任务

### Day 1（8/3 周日）— 实验环境稳定性确认

- [ ] 确认 SUMO 进程不崩溃、内存不溢出（监控 `sumo` 进程 RSS）
- [ ] 重点监控路口 11-20 的运行（0.1s 步长，运行时间更长）
- [ ] 任何路口运行超时或崩溃，立即定位并修复
- [ ] 准备一个轻量监控脚本，定期采样 SUMO 进程内存

```bash
# Windows PowerShell：每 30s 采样一次 sumo 进程内存
while ($true) {
  Get-Process sumo -ErrorAction SilentlyContinue |
    Select-Object Id, @{N='RSS_MB';E={[int]($_.WorkingSet64/1MB)}}
  Start-Sleep 30
}
```

**验证：** 实验运行 1 小时内 `sumo` 进程 RSS 不持续增长（无内存泄漏迹象），无进程崩溃日志。

### Day 2（8/4 周一）— 处理运行中的技术问题

- [ ] 处理高流量路口内存占用高的问题（必要时限制并发数）
- [ ] 评估 0.1s 路口运行时长：3600 步 × 0.1s = 360s 仿真时间，但实际计算量大
- [ ] 若 0.1s 路口太慢，与 EX 协调减少仿真步数（如 1800 步 = 180s）
- [ ] 把调整结论同步到 `experiments/runner.py` 配置

```python
# 估算 0.1s 路口实际计算量
# 1s 路口：3600 步 × ~1ms/步 ≈ 4s
# 0.1s 路口：3600 步 × ~3ms/步 ≈ 11s（车辆交互更密集）
# 若超过 30s/次，360 次实验该路口部分将 > 3h，需考虑减步
```

**验证：** 与 EX 确认步数调整方案后，`python experiments/runner.py --intersection 11 --algo ca_maxpressure` 单次运行时间 < 30s。

### Day 3（8/5 周二）— 并行运行环境（如有第二台机器）

- [ ] 配置第二台机器的并行运行环境（SUMO + 仓库 + 依赖）
- [ ] 编写并行运行脚本，按路口分配实验到两台机器
- [ ] 验证两台机器输出格式一致（避免后续采集出错）

```python
# scripts/split_jobs.py：按路口拆分实验到两台机器
JOBS = [(n, algo, seed) for n in range(1, 21)
        for algo in ["ca_maxpressure", "frap", "mplight"]
        for seed in range(6)]
machine_a = [j for j in JOBS if j[0] <= 10]   # 1s 步长路口给 A
machine_b = [j for j in JOBS if j[0] > 10]    # 0.1s 步长路口给 B
print(f"A: {len(machine_a)} jobs, B: {len(machine_b)} jobs")
```

**验证：** `python scripts/split_jobs.py` 输出 A/B 分配数量，合计 360；两台机器各跑 1 个 job 后输出 XML 字段一致。

### Day 4（8/6 周三）— 输出文件完整性检查

- [ ] 确认所有原始流量实验完成
- [ ] 检查每个实验目录下 `tripinfo.xml + stats.xml + traj.xml` 三件齐全
- [ ] 统计缺失文件并补跑
- [ ] 把检查结果写入 `experiments/results/completeness_report.md`

```python
# scripts/check_outputs.py
from pathlib import Path
required = ["tripinfo.xml", "stats.xml", "traj.xml"]
missing = []
for d in Path("experiments/results").glob("*/*/*"):  # intersection/algo/seed
    if not d.is_dir(): continue
    for f in required:
        if not (d / f).exists() or (d / f).stat().st_size == 0:
            missing.append(f"{d}/{f}")
print(f"缺失/空文件: {len(missing)}")
for m in missing[:20]: print(" -", m)
```

**验证：** `python scripts/check_outputs.py` 输出 `缺失/空文件: 0`（或列出待补跑清单后补跑至 0）。

### Day 5（8/7 周四）— 协助 EX 数据采集

- [ ] 协助 EX 确认 `engine/collector.py` 能正确处理所有 20 路口的输出格式
- [ ] 处理格式差异：不同 SUMO 版本输出的 XML 字段可能略有不同
- [ ] 抽查路口 1、11、16 的 `tripinfo.xml` 字段一致性

```bash
# 抽查不同路口的 tripinfo 字段
head -2 experiments/results/1/ca_maxpressure/0/tripinfo.xml
head -2 experiments/results/11/ca_maxpressure/0/tripinfo.xml
head -2 experiments/results/16/ca_maxpressure/0/tripinfo.xml
# 字段集合应一致（duration / waitingTime / timeLoss 等）
```

**验证：** 三个路口的 `tripinfo.xml` 第二行（首个 `<tripinfo .../>`）属性集合一致；`collector.py` 跑全量采集无 KeyError。

### Day 6（8/8 周五）— Docker 环境搭建（W4 前置）

- [ ] 基于 W2 调研结论选择基础镜像（`ubuntu:22.04`）
- [ ] 编写 `docker/Dockerfile` 初稿：apt 安装 `sumo sumo-tools python3 python3-pip`，pip 安装 `requirements.txt`
- [ ] 测试 Docker 内能否运行 SUMO（`sumo --version`）
- [ ] 测试容器内能否跑通路口 1 的单次仿真

```dockerfile
# docker/Dockerfile（初稿）
FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
    sumo sumo-tools python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt
COPY . /app
WORKDIR /app
CMD ["python3", "experiments/runner.py", "--intersection", "1", "--algo", "ca_maxpressure"]
```

**验证：** `docker build -t ca-mp:dev docker/` 构建成功；`docker run --rm ca-mp:dev sumo --version` 输出版本号。

### Day 7（8/9 周六）— Buffer + Docker 测试完善

- [ ] 修复本周遗留问题
- [ ] 完善 Docker 测试：容器内跑通路口 1 完整实验，输出文件可挂载到宿主机
- [ ] 记录镜像大小初值（W4 目标 < 2GB）

**验证：** `docker run --rm -v ${PWD}/output:/app/output ca-mp:dev` 跑完后宿主机 `output/` 下出现 `tripinfo.xml` 等文件。

## 交付物

| 文件 | 截止日 | 验收标准 |
|------|--------|----------|
| 实验环境稳定运行 | 8/3-8/6 | 无 SUMO 崩溃、无内存溢出 |
| 输出文件完整性检查 | 8/6 | 360 组输出三件齐全（缺失=0） |
| 并行运行脚本（如适用） | 8/5 | 两台机器输出格式一致 |
| `docker/Dockerfile` 初稿 | 8/8 | Docker 内 `sumo --version` 可运行 |

## 协作对接

- 与 **EX** 协调 0.1s 路口步数调整、补跑缺失实验。
- 与 **DB** 确认 `traj.xml` 在长时间运行下文件大小可控。
- 与 **TL** 同步实验进度与 Docker 初稿状态。
