# 算法 A（AA） W4 任务书

> 周期：8/10（周日）- 8/16（周六） | 核心目标：保障基线算法在 1.5 倍压力测试中稳定运行、协助分析高压力结果

## 本周背景

本周引入 **1.5 倍流量压力测试**：通过 `scenes/variant.py` 的 `VariantGenerator` 生成 `TrafficLevel.HIGH`（1.5x）流量变体，验证算法在高压力下的鲁棒性。预期：流量越大，固定配时越不适应，CA-MP 优势越明显——这是报告的重要论点。

---

## 每日任务

### Day 1（8/10 周日）

**监控 1.5 倍流量运行**

- [ ] 监控 FixedTime 与 Actuated 在 1.5 倍流量下的运行
- [ ] 高流量下感应控制可能频繁延长绿灯——确认不超过 `max_green`
- [ ] 若有崩溃立即修复，重点关注排队溢出导致的极端 state

```python
# 高压力下的感应控制：elapsed 触顶 max_green 后必须强制切换
if max_queue > self.queue_threshold and state.elapsed_phase_time < self.max_green:
    return [ControlAction(..., action_type="set_phase_duration", value=5.0,
                          reason="queue_high_extend_green")]
# 一旦 elapsed >= max_green，落入下方切换分支，避免无限延长
```

**验证：** `pytest tests/unit/test_algorithms.py -q` → 全部 passed

### Day 2（8/11 周一）

**检查 1.5 倍流量表现**

- [ ] 固定配时：高流量下排队应显著增加（这是预期的，作为对照）
- [ ] 感应控制：高流量下绿灯可能接近 `max_green` 上限
- [ ] 记录数据，为对比分析准备

```python
# 对比 normal vs high 流量下基线指标
import pandas as pd
normal = pd.read_csv("output/csv/1_normal_fixed_time_s42.csv")
high = pd.read_csv("output/csv/1_high_fixed_time_s42.csv")
print("normal avg_queue:", normal["avg_queue_length"].mean())
print("high   avg_queue:", high["avg_queue_length"].mean())  # 预期显著上升
```

**验证：** `ls output/csv/ | grep high` → 列出 1.5 倍流量变体的 CSV 文件

### Day 3（8/12 周二）

**协助 AB 分析 EWMA 接入效果**

- [ ] 对比有/无 EWMA 的 CA-MP 在路口 1 上的表现
- [ ] 若 EWMA 效果不明显，提供"感应控制视角"的分析（排队动态 vs 流量预测）
- [ ] （时间允许）完善 Webster 基线（可选）

```python
# EWMA 预测（CloudPolicy.predict）：predicted = α*observed + (1-α)*prev
# 感应控制只看当前排队，EWMA 看未来 horizon 流量
# 若两者结论一致，说明 EWMA 接入正确；若背离，需排查 α / horizon 参数
```

**验证：** `pytest tests/unit/test_cloud.py -q` → 全部 passed（CloudPolicy EWMA 行为正常）

### Day 4（8/13 周三）

**汇总高压力基线数据**

- [ ] 汇总原始流量 vs 1.5 倍流量下 FixedTime 的指标变化
- [ ] 汇总原始流量 vs 1.5 倍流量下 Actuated 的指标变化
- [ ] 发给 EX 做统一分析

```python
# 高压力数据汇总维度：
# 算法 × 流量等级(normal/high) × 指标(avg_delay / avg_queue_length / total_throughput)
# 重点确认：high 等级下 FixedTime 指标恶化幅度 > Actuated
```

**验证：** `ls output/csv/ | grep -E "high_(fixed_time|rule_adaptive)"` → 20 路口的高压力基线 CSV 齐全

### Day 5（8/14 周四）

**高压力对比分析**

- [ ] 协助分析：高压力下 CA-MP 的优势是否更明显
- [ ] 验证预期：流量越大，固定配时越不适应，CA-MP 优势越大
- [ ] 为 DA 提供"高压力对比分析"素材（数据 + 结论）

```python
# 报告论点支撑：随流量上升，算法优势排序
# 预期：normal 下三算法差距小；high 下 CA-MP < Actuated < FixedTime（行程时间）
# 若数据支持，作为报告核心论点之一
```

**验证：** `pytest tests/integration/test_experiments.py -q` → 全部 passed

### Day 6（8/15 周五）

**代码最终 review**

- [ ] 确保基线算法代码干净、无遗留 bug
- [ ] 复查 `rule_adaptive.py` 在高压力下的边界（空 queues、elapsed 触顶）
- [ ] 提交代码给 TL

```python
# review 检查点：
# 1. step() 对空 queues 鲁棒（max(..., default=0.0)）
# 2. 相位取模不硬编码：(current_phase + 1) % max(len(queues), 2)
# 3. ControlAction.tls_id 始终取自 state.tls_id
```

**验证：** `pytest tests/unit/test_algorithms.py -q` → 全部 passed

### Day 7（8/16 周六）

**Buffer / 协助**

- [ ] Buffer：修复遗留问题
- [ ] 协助其他组

```python
# 提交前自检
# pytest tests/ -q  # 全量回归
```

**验证：** `pytest tests/ -q` → 全部 passed，无 failure / error

---

## 交付物

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | 基线算法 1.5 倍测试无崩溃 | 8/13 | 20 路口全部成功 |
| 2 | 基线高压力数据汇总 | 8/13 | 发给 EX |
| 3 | 高压力对比分析素材 | 8/14 | 发给 DA |

## 协作对接

- 与 **AB** 对接 EWMA 接入效果分析。
- 向 **EX** 提交高压力基线数据汇总。
- 向 **DA** 提供高压力对比分析素材。
