# W3 任务书：实验组（EX）

> 周期：8/3（周日）- 8/9（周六）
> 核心目标：完成全量实验运行、采集全部指标、生成对比分析

---

## 每日任务

### Day 1（8/3 周日）
1. 启动剩余实验（W2 已预跑路口 1-10 原始流量）：
   - 路口 11-20 × 3 算法 × 原始流量 × 3 种子 = 90 组
   - 后台运行
2. 监控运行进度，处理失败实验（重试）

### Day 2（8/4 周一）
1. 检查进度：目标完成原始流量全部 180 组
2. 对已完成的实验做初步采集：
   - `python experiments/collector.py --results-dir experiments/results`
   - 确认输出 DataFrame 格式正确
3. 标记失败实验，安排补跑

### Day 3（8/5 周二）
1. 补跑失败实验
2. 开始生成对比图表数据：
   - 按 (intersection, algorithm, flow_level) 聚合
   - 计算均值 ± 标准差
3. 将聚合数据发给 DB（生成图表）

### Day 4（8/6 周三）
1. 原始流量 180 组实验全部完成
2. 运行完整采集：
   ```bash
   python experiments/collector.py --results-dir experiments/results --output experiments/results/all_metrics.csv
   ```
3. 运行分析：
   ```bash
   python experiments/analysis.py --input experiments/results/all_metrics.csv
   ```
4. 输出：
   - 20 路口 × 3 算法 × 6 指标的汇总表
   - CA-MP vs FixedTime 改进百分比表
   - t 检验结果（p 值）

### Day 5（8/7 周四）
1. 数据质量检查：
   - 是否有缺失值（某路口某指标为空）
   - 是否有异常值（行程时间为 0 或极大）
   - 3 次重复的标准差是否合理（不应太大）
2. 标记问题数据，与 IA/IB 排查
3. 生成最终版 `all_metrics.csv`

### Day 6（8/8 周五）
1. 生成统计报告：
   - 总体：CA-MP 平均改进 XX%（行程时间）、XX%（排队）、XX%（油耗）
   - 分路口：改进最大/最小的路口
   - 显著性：t 检验 p < 0.05 的路口比例
2. 将统计报告发给 DA（填入报告第四章）
3. 将原始数据发给 DB（生成最终图表）

### Day 7（8/9 周六）
1. Buffer：补跑/修复
2. 整理 `experiments/results/` 目录结构
3. 提交代码和数据给 TL

---

## 交付物清单

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | 原始流量 180 组实验完成 | 8/6 | 全部成功 |
| 2 | `all_metrics.csv` | 8/6 | 180 行 × 6 指标 |
| 3 | 聚合对比表 | 8/6 | 20 路口 × 3 算法 × 均值±std |
| 4 | 改进百分比表 | 8/8 | CA-MP vs FixedTime |
| 5 | t 检验结果 | 8/8 | p 值 |
| 6 | 统计报告 | 8/8 | 发给 DA |
