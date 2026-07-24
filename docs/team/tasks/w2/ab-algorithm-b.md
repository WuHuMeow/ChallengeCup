# 算法 B（AB） W2 任务书

> 周期：7/27（周日）- 8/2（周六） | 核心目标：完善 CA-MP 多路口适配、接入云-边-端消息流、验证创新点效果

## 每日任务

### Day 1（7/27 周日）

- [ ] 修复 W1 联调中发现的 CA-MP bug
- [ ] 确认 `_parse_network()` 能正确解析不同路口的 tlLogic：路口 1（6 相位含 2 黄灯）、路口 16（5 进口道，相位可能更多）、路口 11（相位结构可能不同）
- [ ] 在路口 1 上重新验证：CA-MP 行程时间 < FixedTime

```python
# 不同路口用同一入口验证（_parse_network 必须自适应相位结构）
# python examples/run_demo.py 1 ca_maxpressure
# python examples/run_demo.py 16 ca_maxpressure
# python examples/run_demo.py 11 ca_maxpressure
self._tls_id = f"J{scene.meta.intersection_id}"
self._parse_network(scene.meta.sumo_net)   # 动态读取，不硬编码相位
```

**验证：** `python examples/run_demo.py 1 ca_maxpressure --sumo` 跑通 3600 步，输出 CSV 中 `avg_travel_time` 小于 FixedTime 同条件结果。

### Day 2（7/28 周一）

- [ ] 适配 0.1s 步长路口：每 10 步（=1s）做一次决策，中间步保持当前相位
- [ ] 在路口 11（0.1s）和路口 16（5 进口道）上测试
- [ ] 确认溢出门控在路口 16 的 24m 短边上触发

```python
def step(self, state: JointState) -> List[ControlAction]:
    self._step_count += 1
    # 0.1s 步长路口每 10 步决策一次，其余步保持
    if self._timestep < 1.0 and self._step_count % 10 != 0:
        return [ControlAction(tls_id=state.tls_id, action_type="set_phase",
                              value=self._current_phase, reason="hold")]
    # ...正常决策逻辑（容量归一化 + 溢出门控）
```

**验证：** `python examples/run_demo.py 11 ca_maxpressure --sumo` 跑通且决策动作约每 10 步出现一次（日志中 `set_phase` 频率符合预期）。

### Day 3（7/29 周二）

- [ ] 正式接入云-边-端消息流：确认 `__init__` 中通过 CloudPolicy 能正确接收云端预测参数
- [ ] 验证云端 `CloudPolicy.predict()` 下发 `min_green/max_green/base_green` 后 CA-MP 行为变化
- [ ] 记录消息流是否完整闭环

```python
# cloud/cloud_policy.py：EWMA 预测 + base_green 下发（alpha=0.3, horizon=300）
def predict(self, state: JointState) -> PredictionResult:
    for direction, observed in state.flows.items():
        prev = self._prev_predicted.get(direction, observed)
        predicted[direction] = self.alpha * observed + (1 - self.alpha) * prev
    self._prev_predicted = predicted
    return PredictionResult(horizon_steps=self.horizon,
                            horizon_seconds=float(self.horizon),
                            predicted_flows=predicted)
```

**验证：** `python -m pytest tests/unit/test_cloud.py -q` 全部通过（`predict` 返回 `PredictionResult`、`dispatch_base_green` 返回正 float）。

### Day 4（7/30 周三）

- [ ] 在路口 1 上做三种算法正式对比：FixedTime / Actuated / CA-MP，每种跑 3 次（seed=42, 123, 456）
- [ ] 记录指标：avg_travel_time、avg_queue、throughput、fuel
- [ ] 制作对比表发给 DA 和 EX，验证 CA-MP 在所有指标上优于或等于两个基线

```python
# experiments/runner.py 批量跑批（单路口三算法）
from experiments.runner import run_batch
results = run_batch(intersection_ids=["1"],
                    algorithms=["fixed_time", "actuated", "ca_maxpressure"],
                    seeds=[42, 123, 456], steps=3600)
# 输出 CSV: output/csv/1_normal_<algo>_s<seed>.csv
```

**验证：** `output/csv/` 下生成 9 个 CSV（3 算法 × 3 种子），汇总表中 CA-MP 的 `avg_travel_time` ≤ 两个基线。

### Day 5（7/31 周四）

- [ ] 在路口 16（演示视频主角路口）做重点对比，特别记录溢出门控触发次数、短边排队变化
- [ ] 若 CA-MP 在路口 16 行程时间降低 > 15%，记录为视频素材
- [ ] 调整溢出门控阈值（0.8 ~ 0.95 间测试）：太低会退化为"一直给某方向绿灯"，太高失去保护意义

```yaml
# config/default.yaml（在 0.8~0.95 间调 overflow_occupancy_threshold）
algorithms:
  ca_maxpressure:
    overflow_occupancy_threshold: 0.9
    base_green: 30
    min_green: 10
    max_green: 90
```

**验证：** `python examples/run_demo.py 16 ca_maxpressure --sumo` 跑通，日志中 `overflow gating` 触发次数随阈值单调变化。

### Day 6（8/1 周五）

- [ ] 协助 TL 做 W2 集成验证
- [ ] 确保 CA-MP 在 5 个代表性路口（1 / 11 / 16 等）上无崩溃
- [ ] 提交代码给 TL

```bash
# 代表性路口逐个冒烟（Mock 快速 + SUMO 真仿真）
for id in 1 11 16; do python examples/run_demo.py $id ca_maxpressure; done
```

**验证：** `python -m pytest tests/ -q` 全绿，且 5 个代表性路口 `run_demo.py ... --sumo` 均跑完 3600 步无异常。

### Day 7（8/2 周六）

- [ ] Buffer：修复遗留问题
- [ ] 设计 EWMA 预测模块（W4 实现）：确定输入（过去 N 周期各进口道到达数）、输出（下一周期预测到达量）、融入方式 `adjusted_pressure = (queue + predicted × look_ahead) / capacity`
- [ ] 写设计笔记到 `docs/ewma_design.md`

```python
# EWMA 融入压力的目标形状（W4 落地）
adjusted_pressure = (queue + predicted * look_ahead) / capacity
```

**验证：** `docs/ewma_design.md` 存在且包含输入/输出/融入方式三段定义。

## 交付物

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | CA-MP 0.1s 步长适配 | 7/28 | 路口 11 正常运行，决策频率正确 |
| 2 | CA-MP 5 进口道适配 | 7/28 | 路口 16 正常运行 |
| 3 | 云-边-端消息流闭环 | 7/29 | CloudPolicy 影响 CA-MP 行为，`tests/unit/test_cloud.py` 通过 |
| 4 | 路口 1 三算法对比数据 | 7/30 | CA-MP 优于基线（9 个 CSV + 对比表） |
| 5 | 路口 16 重点对比 | 7/31 | 溢出门控触发、行程时间降低 > 15% |
| 6 | `docs/ewma_design.md` | 8/2 | EWMA 设计笔记（输入/输出/融入方式） |

## 协作对接

- 与 **TL** 完成 W2 集成验证，确认云-边-端消息流贯通。
- 将路口 1 / 16 对比表发给 **DA**（报告素材）和 **EX**（实验复核）。
- 与 **DB** 对接路口 16 视频素材（溢出门控触发片段）。
