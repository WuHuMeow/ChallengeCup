# W3 任务书：仿真基础设施 A（IA）

> 周期：8/3（周日）- 8/9（周六）
> 核心目标：保障全量实验运行环境稳定、处理运行中的技术问题

---

## 每日任务

### Day 1（8/3 周日）
1. 确认实验运行环境稳定：SUMO 进程不崩溃、内存不溢出
2. 监控路口 11-20 的运行（0.1s 步长路口运行时间更长）
3. 如果有路口运行超时或崩溃，立即修复

### Day 2（8/4 周一）
1. 处理实验运行中的技术问题：
   - 某些路口可能因流量过大导致 SUMO 内存占用高
   - 某些路口可能因步长 0.1s 导致运行时间过长（3600 步 × 0.1s = 360s 仿真时间，但实际计算量大）
2. 优化方案：如果 0.1s 路口太慢，考虑减少仿真步数（如 1800 步 = 180s）
3. 与 EX 协调调整

### Day 3（8/5 周二）
1. 如果有第二台机器，配置并行运行环境
2. 将部分实验分配到第二台机器
3. 编写并行运行脚本（按路口分配）

### Day 4（8/6 周三）
1. 确认所有原始流量实验完成
2. 检查输出文件完整性：每个实验目录下都有 tripinfo.xml + stats.xml + traj.xml
3. 统计缺失文件，补跑

### Day 5（8/7 周四）
1. 协助 EX 做数据采集：确认 collector.py 能正确处理所有 20 路口的输出格式
2. 处理格式差异（不同 SUMO 版本输出的 XML 字段可能略有不同）

### Day 6（8/8 周五）
1. 开始 Docker 环境搭建（W4 任务前置）：
   - 基于 IA 之前的调研，选择基础镜像
   - 编写 Dockerfile 初稿：
     ```dockerfile
     FROM ubuntu:22.04
     RUN apt-get update && apt-get install -y sumo sumo-tools python3 python3-pip
     COPY requirements.txt .
     RUN pip3 install -r requirements.txt
     COPY . /app
     WORKDIR /app
     CMD ["python3", "experiments/runner.py", "--intersection", "1", "--algo", "ca_maxpressure"]
     ```
2. 测试 Docker 内能否运行 SUMO

### Day 7（8/9 周六）
1. Buffer：修复遗留问题
2. 完善 Docker 测试

---

## 交付物清单

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | 实验环境稳定运行 | 8/3-8/6 | 无崩溃 |
| 2 | 输出文件完整性检查 | 8/6 | 360 组输出完整 |
| 3 | Dockerfile 初稿 | 8/8 | Docker 内 SUMO 可运行 |
