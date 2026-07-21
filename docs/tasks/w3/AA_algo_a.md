# 算法 A（AA） W3 任务书

> 周期：8/3（周日）- 8/9（周六） | 核心目标：保障 FixedTime 与 Actuated 在全量实验中稳定运行、协助分析异常结果

---

## 每日任务

### Day 1（8/3 周日）

**监控全量实验运行状态**

- [ ] 监控 FixedTime 与 Actuated 在全量实验（20 路口 × 3 种子）中的运行状态
- [ ] 若某路口基线崩溃，立即定位并修复
- [ ] 特别关注 0.1s 步长路口（11-13、15-20）的感应控制，确认 `elapsed_phase_time` 比较逻辑正确
- [ ] 记录任何崩溃栈信息，便于回溯

```python
# 监控关注点：基线算法在批量跑批中不应抛异常
# experiments/runner.py 会遍历 20 路口 × 3 算法 × 3 种子
# 任一组合崩溃都会中断整批，需保证 step() 对空 queues / 极端 state 鲁棒
max_queue = max((q.queue_length for q in state.queues), default=0.0)  # default 防空
```

**验证：** `pytest tests/test_algorithms.py -q` → 全部 passed（含空排队等边界用例）

### Day 2（8/4 周一）

**检查已完成实验结果**

- [ ] 检查固定配时指标是否合理：不应出现 0 车辆通过的情况（`total_throughput > 0`）
- [ ] 检查感应控制的绿灯时长分布是否在 `min_green ~ max_green` 范围内
- [ ] 标记异常结果（如某路口排队恒为 0 或 throughput 异常）
- [ ] 将异常清单报告 TL

```python
# 用 pandas 抽查 CSV 指标合理性
import pandas as pd
df = pd.read_csv("output/csv/1_fixed_time.csv")
assert df["total_throughput"].sum() > 0, "固定配时不应 0 车辆通过"
print(df[["avg_queue_length", "max_queue_length", "total_throughput"]].describe())
```

**验证：** `python -c "import pandas as pd; df=pd.read_csv('output/csv/1_fixed_time.csv'); print(df['total_throughput'].sum())"` → 输出大于 0 的数值

### Day 3（8/5 周二）

**协助 AB 分析 CA-MP 异常路口**

- [ ] 对比 CA-MP 与 Actuated 在效果不佳路口的行为差异（相位切换、绿灯时长）
- [ ] 判断是参数问题（min/max_green、阈值）还是算法逻辑问题（压力计算）
- [ ] 若是参数问题，给出调整建议

```python
# 同一路口、相同 state 下对比两算法输出
# Actuated: 基于 max(queue_length) 与 queue_threshold
# CA-MP:    基于上下游压力差
# 若 CA-MP 频繁切相位而 Actuated 稳定，多半是压力计算/相位映射问题
```

**验证：** `python examples/run_demo.py {异常路口} actuated` → Mock 链路跑通，输出 `链路验证完成`

### Day 4（8/6 周三）

**汇总基线指标**

- [ ] 全量实验完成后，用 `engine/collector.py` 检查基线指标
- [ ] 汇总 20 路口 FixedTime 的平均行程时间分布
- [ ] 汇总 20 路口 Actuated 的平均行程时间分布
- [ ] 确认基线数据合理（作为对比基准），发给 EX

```python
# 基线数据汇总：20 路口 × 2 基线
# 关注 avg_delay / avg_queue_length / total_throughput 三类指标
# 确认 FixedTime 与 Actuated 的分布合理，作为 CA-MP 的对比基准
```

**验证：** `ls output/csv/ | grep -E "fixed_time|rule_adaptive"` → 列出 20 路口对应的基线 CSV 文件

### Day 5（8/7 周四）

**协助 EX 做数据质量检查**

- [ ] 排查是否有路口 FixedTime 反而优于 CA-MP（异常信号）
- [ ] 排查是否有路口 Actuated 崩溃或输出异常
- [ ] 对异常路口提供解释（如：该路口流量极低，任何算法差异不大）

```python
# 异常判定示例：FixedTime 指标优于 CA-MP 时需复核
# 低流量路口（如流量极低的路口）算法差异本就不显著，属正常现象
# 高流量路口若 FixedTime 反超，则需排查 CA-MP 压力计算
```

**验证：** `pytest tests/test_experiments.py -q` → 全部 passed

### Day 6（8/8 周五）

**Webster 基线（可选）**

- [ ] （可选）从 `.xlsx` 读取流量与饱和流率
- [ ] （可选）用 Webster 公式计算最优周期与绿信比，实现 `algorithms/webster.py`
- [ ] 若时间不够则跳过——两个基线已足够对比

```python
# Webster 基线骨架（可选实现）
# 1. parse_timing_excel / pandas 读取流量与饱和流率
# 2. C0 = (1.5*L + 5) / (1 - Y); g_i = (C0 - L) * y_i / Y
# 3. 继承 BaseControlAlgorithm，init() 时写入 SUMO 配时（参照 fixed_time._apply_excel_timing）
```

**验证：** （若实现）`python examples/run_fixed_time.py 1` 替换为 webster 入口后跑通；否则本日无强制验证

### Day 7（8/9 周六）

**Buffer / 提交**

- [ ] Buffer：修复遗留问题
- [ ] 跑一遍接口契约测试，确认无回归
- [ ] 提交代码给 TL

```python
# 提交前自检：接口契约 + 实验跑批测试
# pytest tests/test_algorithms.py tests/test_experiments.py -q
```

**验证：** `pytest tests/test_algorithms.py tests/test_experiments.py -q` → 全部 passed

---

## 交付物

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | 基线算法全量运行无崩溃 | 8/6 | 20 路口 × 2 基线 × 3 种子全部成功 |
| 2 | 异常结果分析 | 8/7 | 每个异常有解释 |
| 3 | Webster 基线（可选） | 8/8 | 如果实现，路口 1 可运行 |

## 协作对接

- 与 **AB** 对接 CA-MP 异常路口的归因分析。
- 向 **EX** 提交基线指标汇总，配合数据质量检查。
- 异常清单与修复进展同步 **TL**。
