# W2 任务书：实验组（EX）

> 周期：7/27（周日）- 8/2（周六）
> 核心目标：完成 runner.py 联调、验证采集脚本、开始预跑实验

---

## 每日任务

### Day 1（7/27 周日）

1. 与 IB 联调 runner.py：
   - 确认 main.py 支持 `--seed`、`--flow-multiplier`、`--output-dir`
   - 用路口 1 跑一次完整实验：
     ```bash
     python experiments/runner.py --intersection 1 --algo ca_maxpressure --flow original --seed 42
     ```
   - 验证输出目录下有：tripinfo.xml、stats.xml、traj.xml、simulation_log.csv
2. 修复联调问题

### Day 2（7/28 周一）

1. 验证 collector.py 能正确采集所有指标：
   - 用 Day 1 的输出文件测试
   - 确认 6 项指标都有值：avg_travel_time, avg_queue_length, throughput, fuel_consumption, avg_delay, avg_stops
2. 验证 analysis.py 的聚合功能：
   - 用假数据（3 次重复）测试 aggregate_results()
   - 确认输出均值 ± 标准差
3. 修复采集脚本的 bug

### Day 3（7/29 周二）

1. 完善 runner.py：
   - 添加断点续跑功能（如果中途中断，能从上次位置继续）
   - 添加进度显示：`[42/360] Running: i5_ca_maxpressure_high_pressure_s123`
   - 添加失败重试（最多重试 2 次）
   - 添加结果汇总：每跑完一组，追加到 `experiments/results/summary.csv`
2. 测试：跑 5 组实验（路口 1 × 3 算法 × 1 流量 × 1 种子 + 2 组额外），确认断点续跑正常

### Day 4（7/30 周三）

1. 验证流量放大功能：
   - 用 `--flow-multiplier 1.5` 跑路口 1
   - 对比原始流量和 1.5 倍流量的输出：车辆数应该增加约 50%
   - 确认 scale_flow.py 正确工作
2. 如果流量放大有问题，与 IB 协调修复

### Day 5（7/31 周四）

1. **开始预跑实验**（利用 TL/AB 在路口 1 验证通过的信心）：
   - 先跑路口 1-5 × 3 算法 × 原始流量 × 3 种子 = 45 组
   - 后台运行，不阻塞其他工作
   ```bash
   python experiments/runner.py --intersections 1-5 --flow original &
   ```
2. 监控运行状态，记录失败的实验

### Day 6（8/1 周五）

1. 检查预跑结果：
   - 45 组实验是否全部成功
   - 用 collector.py 采集指标
   - 用 analysis.py 生成初步对比表
2. 将初步结果发给 TL 和 DA：
   - "路口 1-5 的 CA-MP vs FixedTime 对比数据已出"
3. 如果有异常结果（如 CA-MP 反而更差），立即报告 AB

### Day 7（8/2 周六）

1. 继续预跑：路口 6-10 × 3 算法 × 原始流量 × 3 种子 = 45 组
2. 编写 `experiments/README.md` 完善版：
   - 如何运行实验
   - 如何采集指标
   - 如何生成对比表
   - 常见问题
3. 提交代码给 TL

---

## 交付物清单

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | runner.py 联调通过 | 7/27 | 单次实验输出完整 |
| 2 | collector.py 验证通过 | 7/28 | 6 项指标正确采集 |
| 3 | runner.py 断点续跑 | 7/29 | 中断后能继续 |
| 4 | 流量放大验证 | 7/30 | 1.5 倍流量车辆数增加 ~50% |
| 5 | 路口 1-5 预跑完成 | 8/1 | 45 组实验成功 |
| 6 | 路口 6-10 预跑完成 | 8/2 | 45 组实验成功 |
| 7 | `experiments/README.md` | 8/2 | 使用说明完整 |

---

## 注意事项

- W2 开始预跑是为了给 W3 减负——360 组实验如果全堆到 W3 会来不及
- 预跑只跑"原始流量"，1.5 倍压力测试留到 W4
- 如果机器时间不够，优先保证路口 1、11、16（重点路口）
- 每次实验失败要记录原因（超时？内存不足？SUMO 崩溃？）
- 后台跑实验时不要占用机器做其他重计算
