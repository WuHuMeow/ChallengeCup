# 算法 A（AA） W2 任务书

> 周期：7/27（周日）- 8/2（周六） | 核心目标：完善感应控制算法（0.1s 步长 + 多进口道适配）、接入 CloudPolicy 调参、协助 AB 调试 CA-MP

## 本周背景

本周引入两个新概念：

- **CloudPolicy 调参**（`cloud/cloud_policy.py`）：边缘算法通过 `CloudPolicy.predict(state)` 获取 EWMA 流量预测，据此动态调整 `min_green` / `max_green`，使三种算法都能用统一的云端调参通道，保证公平对比。
- **0.1s 步长适配**：路口 11-13、15-20 的仿真步长为 0.1s。算法不应自己累加时间，而应直接使用 `JointState.elapsed_phase_time`（由 engine 按真实步长维护）。

---

## 每日任务

### Day 1（7/27 周日）

**修复 W1 遗留并复验感应控制**

- [ ] 修复 W1 遗留的 RuleAdaptiveAlgorithm 问题（如有）
- [ ] 路口 1 复验：绿灯时长在 `min_green ~ max_green` 之间动态变化
- [ ] 确认排队低于 `queue_threshold` 时能提前切换相位（日志 `reason="queue_low_next_phase"`）
- [ ] 与 TL 的固定配时数据核对：感应控制应略优于固定配时

```python
# 复验关注点：step() 的两类输出动作
# 延长绿灯：action_type="set_phase_duration", reason="queue_high_extend_green"
# 切换相位：action_type="set_phase",         reason="queue_low_next_phase"
# 最小绿灯内：返回 []（不干预）
```

**验证：** `python examples/run_rule_adaptive.py 1` → 输出 `仿真完成`，日志中同时出现 `queue_high_extend_green` 与 `queue_low_next_phase`

### Day 2（7/28 周一）

**适配 0.1s 步长与 5 进口道路口**

- [ ] 确认 RuleAdaptiveAlgorithm 不自己累加 `_green_elapsed`，统一使用 `state.elapsed_phase_time`
- [ ] 若历史实现存在 `self._green_elapsed += self._timestep`，改为读取 `JointState.elapsed_phase_time`
- [ ] 在路口 11（0.1s 步长）上测试感应控制
- [ ] 在路口 16（5 进口道）上测试感应控制，确认相位取模逻辑正确

```python
# 正确做法：时间由 JointState 提供，算法无需感知步长
def step(self, state: JointState) -> List[ControlAction]:
    if state.elapsed_phase_time < self.min_green:
        return []
    # 不要写 self._green_elapsed += self._timestep
    # elapsed_phase_time 在 1s 路口每步 +1，在 0.1s 路口每步 +0.1
```

**验证：** `python examples/run_rule_adaptive.py 11 && python examples/run_rule_adaptive.py 16` → 两条命令均输出 `仿真完成`，无崩溃

### Day 3（7/29 周二）

**协助 AB 调试 CA-MP**

- [ ] 对比 CA-MP 与 RuleAdaptiveAlgorithm 在路口 1 上的行为差异（相位切换频率、绿灯时长分布）
- [ ] 若 CA-MP 效果不如预期，协助排查：压力计算、相位映射、容量计算是否正确
- [ ] 为 AB 提供"感应控制 vs CA-MP"的对比视角

```python
# 对比维度：两种算法在相同 state 下的输出差异
# RuleAdaptive：基于 max(queue_length) 与阈值比较
# CA-MP：基于上下游压力差选择相位
# 排查时打印 state.current_phase / state.queues，对照两算法的 reason 字段
```

**验证：** `python examples/run_demo.py 1 ca_maxpressure` → Mock 链路跑通 10 步，输出 `链路验证完成`

### Day 4（7/30 周三）

**接入 CloudPolicy 参数可配置性**

- [ ] 为 RuleAdaptiveAlgorithm 增加 `cloud_policy: CloudPolicy | None = None` 构造参数
- [ ] 在 `step()` 中调用 `cloud_policy.predict(state)`，用预测流量调整 `max_green`（高预测流量拉长绿灯）
- [ ] 保持 `min_green` / `max_green` / `queue_threshold` 仍可从 `config/default.yaml` 读取（无 CloudPolicy 时回退默认）
- [ ] 确保三种算法都能用 CloudPolicy 统一调参，公平对比

```python
# 通过 CloudPolicy.predict() 获取未来流量预测，再据此调整绿灯上限
prediction = cloud_policy.predict(state) if cloud_policy else None
if prediction is not None:
    avg_predicted = sum(prediction.predicted_flows.values()) / max(
        len(prediction.predicted_flows), 1)
    # 高预测流量 → 拉长绿灯，低预测流量 → 缩短绿灯
    self.max_green = 80 if avg_predicted > 0.7 else 60
```

**验证：** `pytest tests/unit/test_algorithms.py::test_rule_adaptive_returns_control_actions -q` → `1 passed`（接入 CloudPolicy 后接口契约不破）

### Day 5（7/31 周四）

**5 个代表性路口测试**

- [ ] 在路口 1（标准十字、1s 步长）跑通 RuleAdaptive
- [ ] 在路口 11（0.1s 步长）、路口 16（5 进口道、24m 短边）跑通
- [ ] 在路口 5、路口 20（随机代表）跑通
- [ ] 记录每个路口的运行状态与指标，向 EX 报告异常路口（如有）

```python
# 批量验证脚本片段：遍历代表路口
for iid in ["1", "11", "16", "5", "20"]:
    scene = SceneRegistry().get_scene(iid)
    runner = SimulationRunner(scene, RuleAdaptiveAlgorithm())
    runner.run(steps=3600)
    print(iid, "ok ->", runner.output_csv)
```

**验证：** 上述 5 个路口逐一运行 `python examples/run_rule_adaptive.py {id}` → 全部输出 `仿真完成`，无异常退出

### Day 6（8/1 周五）

**W2 集成验证**

- [ ] 协助 TL 做 W2 集成验证
- [ ] 确保 `--algo actuated` 在 `experiments/runner.py` 中正确工作（`ALGORITHM_MAP["actuated"]`）
- [ ] 提交代码给 TL

```python
# experiments/runner.py 中 actuated 映射到 RuleAdaptiveAlgorithm
ALGORITHM_MAP: Dict[str, type[BaseControlAlgorithm]] = {
    "fixed_time": FixedTimeAlgorithm,
    "actuated": RuleAdaptiveAlgorithm,   # 本周需保证此入口可用
    "ca_maxpressure": CAMaxPressureAlgorithm,
}
```

**验证：** `pytest tests/integration/test_experiments.py -q` → 全部 passed

### Day 7（8/2 周六）

**Buffer / Webster 预研**

- [ ] Buffer：修复遗留问题
- [ ] 阅读 Webster 公式（可选第三基线，W4 决定是否实现）：最优周期 `C₀ = (1.5L + 5) / (1 - Y)`，各相位绿灯 `gᵢ = (C₀ - L) × yᵢ / Y`
- [ ] 记录公式与所需输入（流量、饱和流率），W4 评估实现成本

```python
# Webster 公式记录（W4 评估，本周不实现）
# C0 = (1.5 * L + 5) / (1 - Y)        # 最优周期，L=总损失时间，Y=各相位流量比之和
# g_i = (C0 - L) * y_i / Y            # 第 i 相位绿灯时长
# 输入来源：.xlsx 中的流量与饱和流率
```

**验证：** `pytest tests/unit/test_algorithms.py -q` → 全部 passed（本周改动无回归）

---

## 交付物

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | RuleAdaptiveAlgorithm 0.1s 适配 | 7/28 | 路口 11 正常运行 |
| 2 | RuleAdaptiveAlgorithm 5 进口道适配 | 7/28 | 路口 16 正常运行 |
| 3 | CloudPolicy 参数接收 | 7/30 | 感应控制支持云端调参 |
| 4 | 5 路口测试报告 | 7/31 | 无崩溃、指标合理 |

## 协作对接

- 与 **AB** 对接 CA-MP 调试，提供感应控制对比视角。
- 与 **IB** 确认 `CloudPolicy` 注入方式与 `experiments/runner.py` 的 `--algo actuated` 入口。
- 向 **EX** 报告 5 路口测试中的异常表现。
