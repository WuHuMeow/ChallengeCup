# W2 任务书：Tech Lead（TL）

> 周期：7/27（周日）- 8/2（周六）
> 核心目标：完成云-边-端联调、确保三种算法在路口 1 出对比数据

---

## 每日任务

### Day 1（7/27 周日）

1. 检查 W1 交付物完整性：
   - IA：20 路口是否全部可运行
   - IB：simulator.py + edge_node.py + cloud.py 是否合入
   - AA：fixed_time.py + actuated.py 是否合入
   - AB：ca_max_pressure.py 是否合入
   - EX：config.yaml + runner.py 框架是否就绪
2. 解决 W1 遗留的集成问题
3. 确认 main.py 支持 `--algo fixed_time/actuated/ca_maxpressure` 三选一

### Day 2（7/28 周一）

1. 协调 IB 为 main.py 添加 EX 需要的参数：`--seed`、`--flow-multiplier`、`--output-dir`
2. 验证：`python src/platform/main.py --intersection 1 --algo ca_maxpressure --steps 3600 --seed 42 --output-dir experiments/results/test_run`
3. 确认输出目录下有 tripinfo.xml 和 stats.xml

### Day 3（7/29 周二）

1. 在路口 1 上跑三种算法的完整对比：
   - `--algo fixed_time` → 记录 stats
   - `--algo actuated` → 记录 stats
   - `--algo ca_maxpressure` → 记录 stats
2. 验证 CA-MP 的平均行程时间 < 固定配时（如果不满足，与 AB 排查原因）
3. 将对比数据发给 DA（报告素材）和 DB（图表素材）

### Day 4（7/30 周三）

1. Review AB 的 CA-MP 代码质量：
   - 溢出门控逻辑是否正确
   - 容量计算是否合理（length / 7.5）
   - 边界情况处理（无车时、压力全为 0 时）
2. Review IB 的云-边-端消息流：
   - V2XMessage 是否每步都产生
   - CloudCoordinator 是否周期性下发 CloudCommand
   - EdgeNode 是否正确转发
3. 提出修改意见，跟踪修复

### Day 5（7/31 周四）

1. 在路口 16（重点路口）上验证三种算法：
   - 特别关注：溢出门控是否在 24m 短边上触发
   - 记录触发频率和效果
2. 在路口 11（0.1s 步长）上验证：
   - 确认决策频率正确（不会每 0.1s 切一次相位）
3. 记录问题，与 AB/IB 修复

### Day 6（8/1 周五）

1. 打 tag：`git tag v0.2-w2-complete`
2. 编写 W2 周报
3. 确认 W3 全量实验的前置条件：
   - runner.py 能生成 360 组实验
   - main.py 支持所有需要的参数
   - 输出目录结构正确
4. 与 EX 确认：W3 第一天就能开始批量跑实验

### Day 7（8/2 周六）

1. Buffer：处理本周遗留 bug
2. 开始规划 W3 的实验运行顺序（先跑哪些路口、是否需要多台机器）
3. 确认 DA/DB 的 W2 产出（报告框架更新、图表测试）

---

## 交付物清单

| # | 交付物 | 截止日 | 验收标准 |
|---|--------|--------|----------|
| 1 | 三种算法在路口 1 对比数据 | 7/29 | CA-MP 行程时间 < FixedTime |
| 2 | 路口 16 验证通过 | 7/31 | 溢出门控触发 |
| 3 | 路口 11 验证通过 | 7/31 | 0.1s 步长正常 |
| 4 | W3 前置条件确认 | 8/1 | runner.py 可运行 |
| 5 | git tag v0.2 | 8/1 | 代码稳定 |
