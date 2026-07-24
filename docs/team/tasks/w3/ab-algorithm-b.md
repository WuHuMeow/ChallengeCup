# 算法 B（AB） W3 任务书

> 周期：8/3（周日）- 8/9（周六） | 核心目标：监控 CA-MP 全量运行、分析效果、为 W4 EWMA 做准备

## 每日任务

### Day 1（8/3 周日）

- [ ] 监控 CA-MP 在全量实验中的运行状态
- [ ] 特别关注：溢出门控触发频率（不应太高也不应太低）、是否有路口陷入"一直给同一方向绿灯"的死循环
- [ ] 发现问题立即修复

```bash
# 全量跑批由 EX 触发，AB 监控 ca_maxpressure 相关运行
python -c "from experiments.runner import run_batch; run_batch(algorithms=['ca_maxpressure'])"
```

**验证：** `output/csv/` 下所有 `*_ca_maxpressure_*.csv` 均完整生成（20 路口 × 3 种子），无中途崩溃日志。

### Day 2（8/4 周一）

- [ ] 检查已完成实验的 CA-MP 指标：与 FixedTime 对比行程时间是否降低、与 Actuated 对比是否仍有优势
- [ ] 记录 CA-MP 表现最好和最差的路口
- [ ] 分析原因：最好可能是短边路口（容量归一化生效），最差可能是流量极低路口（任何算法差异不大）

```python
# 改进百分比计算口径
improvement = (fixed_travel_time - ca_mp_travel_time) / fixed_travel_time * 100
```

**验证：** 产出一张 20 路口 CA-MP vs FixedTime / Actuated 的指标对照表，最好/最差路口各有标注。

### Day 3（8/5 周二）

- [ ] 深入分析路口 16（重点路口）实验结果：溢出门控触发次数、短边（24m）排队变化、CA-MP vs FixedTime 行程时间差异
- [ ] 将分析结果发给 DA（报告素材）和 DB（视频素材）

```bash
# 路口 16 单点复跑，观察溢出门控
python examples/run_demo.py 16 ca_maxpressure --sumo
```

**验证：** 路口 16 分析文档包含三项数据：溢出门控触发次数、短边排队曲线、行程时间差异百分比。

### Day 4（8/6 周三）

- [ ] 全量实验完成后汇总 CA-MP 的 20 路口表现：计算每路口改进百分比 `(fixed − ca_mp) / fixed × 100%`
- [ ] 排序：哪些路口改进最大、哪些最小，计算总体平均改进
- [ ] 将数据发给 EX 和 DA

```python
# 汇总口径（逐路口）
for iid in range(1, 21):
    imp = (fixed[iid] - ca_mp[iid]) / fixed[iid] * 100
    print(f"路口{iid}: {imp:.1f}%")
```

**验证：** 产出 20 路口改进百分比排序表 + 总体平均改进数值，发送 EX/DA 确认。

### Day 5（8/7 周四）

- [ ] 分析 CA-MP 效果不佳的路口（如有）：参数问题（overflow_threshold 不适配）？流量问题（流量太低无优化空间）？拓扑问题（路口结构特殊）？
- [ ] 提出 W4 调优方案：是否按路口类型分组设参、是否调整 overflow_threshold

```yaml
# 待评估的调参维度（config/default.yaml）
algorithms:
  ca_maxpressure:
    overflow_occupancy_threshold: 0.9   # 候选 0.8 / 0.85 / 0.95
```

**验证：** 每个异常路口有一条归因解释，并形成 W4 调优方案清单。

### Day 6（8/8 周五）

- [ ] 完善 EWMA 设计（`docs/ewma_design.md`）：确定 alpha 值（建议 0.3-0.5）、look_ahead 步数（建议 1-2 周期）、融入方式 `adjusted_queue = queue + predicted_arrival × look_ahead`
- [ ] 写伪代码
- [ ] 与 TL 确认 W4 实现计划

```python
# EWMA 伪代码（W4 在 cloud/cloud_policy.py 实现，alpha 默认 0.3）
predicted = alpha * observed + (1 - alpha) * prev_predicted
adjusted_queue = queue + predicted * look_ahead
```

**验证：** `docs/ewma_design.md` 含 alpha / look_ahead 取值依据与伪代码，TL 确认 W4 计划。

### Day 7（8/9 周六）

- [ ] Buffer：修复遗留问题
- [ ] 提交代码给 TL

```bash
python -m pytest tests/ -q
```

**验证：** `python -m pytest tests/ -q` 全绿后提交 TL。

## 交付物

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | CA-MP 全量运行无崩溃 | 8/6 | 20 路口 × 3 种子全部成功 |
| 2 | 路口 16 深入分析 | 8/5 | 溢出门控数据 + 效果数据 |
| 3 | 20 路口改进百分比汇总 | 8/6 | 排序表 + 总体平均 |
| 4 | 异常路口分析 | 8/7 | 每个异常有归因解释 |
| 5 | `docs/ewma_design.md` 完善 | 8/8 | 含伪代码和参数选择 |

## 协作对接

- 与 **EX** 对齐全量跑批结果与改进百分比口径。
- 向 **DA** 提供路口 16 与 20 路口汇总数据（报告素材），向 **DB** 提供视频素材。
- 与 **TL** 确认 W4 EWMA 实现计划。
