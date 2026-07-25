# 算法 B（AB） W4 任务书

> 周期：8/10（周日）- 8/16（周六） | 核心目标：实现 EWMA 流量预测并接入 CA-MP、分析 1.5 倍压力测试结果

## 本周背景

EWMA（指数加权移动平均）是云端流量预测的轻量实现，已以 `alpha=0.3` 落地在 `cloud/cloud_policy.py` 的 `predict()` 中（公式 `predicted(t+1) = α × observed(t) + (1−α) × predicted(t)`）。本周把预测结果正式融入 CA-MP 的压力计算，并用 `ml/train.py` 做参数校准。EWMA 相比 LSTM 的优势：轻量、无需训练、3 行代码、适合边缘部署。

## 每日任务

### Day 1（8/10 周日）

- [ ] 实现 EWMA 预测模块 `algorithms/ewma_predictor.py`（每周期更新一次，不是每步）
- [ ] 在 CA-MP 的 `_compute_normalized_pressures()` 中接入预测值
- [ ] alpha 默认与 `config/default.yaml` 的 `ewma_alpha: 0.3` 对齐

```python
# algorithms/ewma_predictor.py
class EWMAPredictor:
    """指数加权移动平均流量预测。"""
    def __init__(self, alpha: float = 0.3, history_window: int = 3):
        self.alpha = alpha
        self.history_window = history_window
        self._history: dict[str, list[float]] = {}
        self._predictions: dict[str, float] = {}

    def update(self, arrivals: dict[str, int]) -> None:
        """每周期更新一次（不是每步）。"""
        for lane_id, count in arrivals.items():
            prev = self._predictions.get(lane_id, float(count))
            self._predictions[lane_id] = self.alpha * count + (1 - self.alpha) * prev

    def predict(self, lane_id: str) -> float:
        return self._predictions.get(lane_id, 0.0)
```

```python
# 在 CA-MP _compute_normalized_pressures() 中接入（look_ahead = 1）
predicted = self.predictor.predict(lane_id)
adjusted_queue = queue + predicted * self.look_ahead
norm_pressure = adjusted_queue / capacity
```

**验证：** `python -m pytest tests/test_cloud.py -q` 通过，且单元构造 `EWMAPredictor(alpha=0.3)` 后 `predict()` 对首次更新返回观测值。

### Day 2（8/11 周一）

- [ ] 在路口 1 上验证 EWMA 效果：对比有/无 EWMA 的 CA-MP，预期在流量波动时表现更好（提前切换相位）
- [ ] 若效果不明显或引入不稳定，在 0.2-0.6 间调整 alpha
- [ ] 与 TL 确认是否保留 EWMA

```bash
python examples/run_demo.py 1 ca_maxpressure --sumo
```

**验证：** 路口 1 有/无 EWMA 两组 CSV 对比，接入 EWMA 后 `avg_travel_time` 不退化（≥ 持平）。

### Day 3（8/12 周二）

- [ ] 在路口 16 上验证 EWMA：短边路口流量波动大，EWMA 应有明显效果
- [ ] 在路口 11（0.1s 步长）上验证：确认 EWMA 更新频率正确（每周期更新，不是每 0.1s）
- [ ] 修复兼容性问题

```bash
python examples/run_demo.py 16 ca_maxpressure --sumo
python examples/run_demo.py 11 ca_maxpressure --sumo
```

**验证：** 路口 16、11 均跑通 3600 步无崩溃，EWMA `update()` 调用频率为每周期一次。

### Day 4（8/13 周三）

- [ ] 1.5 倍压力测试完成后，分析 CA-MP（含 EWMA）表现：高压力下 EWMA 预测是否更准确（流量大、规律性强）
- [ ] 计算 1.5 倍流量下的改进百分比
- [ ] 与 W3 原始流量结果对比：高压力下优势是否更大

```python
# 1.5 倍流量由 VariantGenerator 生成（experiments/runner.py，level=HIGH）
from core.types import TrafficLevel
from experiments.runner import run_batch
run_batch(intersection_ids=["1", "16"], algorithms=["ca_maxpressure"],
          levels=[TrafficLevel.HIGH], seeds=[42, 123, 456])
```

**验证：** 产出 1.5 倍流量下 CA-MP 改进百分比，并与 W3 原始流量数值形成对照。

### Day 5（8/14 周四）

- [ ] 参数敏感性分析（为报告准备）：overflow_threshold（0.8 / 0.85 / 0.9 / 0.95）与 EWMA alpha（0.2 / 0.3 / 0.4 / 0.5 / 0.6）的效果对比
- [ ] 在路口 1 和路口 16 上各跑一组
- [ ] 记录结果发给 EX 和 DA

```python
# ml/train.py 做 EWMA 参数校准（alpha 扫描）
from ml.train import train
for alpha in [0.2, 0.3, 0.4, 0.5, 0.6]:
    params = train(features, labels, alpha=alpha)
```

**验证：** 产出 threshold × alpha 敏感性对比表（路口 1 / 16 各一份），发送 EX/DA。

### Day 6（8/15 周五）

- [ ] 最终代码整理：EWMA 模块有完整 docstring、参数可通过 CloudPolicy 动态调整
- [ ] 确保无 EWMA 时 CA-MP 退化为 W3 版本（向后兼容）
- [ ] 提交代码给 TL

```python
# cloud/cloud_policy.py 已支持 alpha 动态读取与状态重置
self.alpha = cfg.get("ewma_alpha", 0.3)
def reset(self) -> None:
    self._prev_predicted = {}
```

**验证：** `python -m pytest tests/ -q` 全绿，关闭 EWMA 时 CA-MP 输出与 W3 版本一致。

### Day 7（8/16 周六）

- [ ] Buffer：修复遗留问题
- [ ] 为 DA 准备"算法原理"章节的 EWMA 部分素材（公式 + 效果图）

```text
EWMA: predicted(t+1) = α × observed(t) + (1−α) × predicted(t),  α = 0.3
```

**验证：** 向 DA 交付 EWMA 公式说明 + 一张效果对比图。

## 交付物

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | `algorithms/ewma_predictor.py` | 8/10 | EWMA 预测模块完整，alpha 与配置对齐 |
| 2 | CA-MP 接入 EWMA | 8/11 | 路口 1 效果不退化 |
| 3 | 多路口 EWMA 验证 | 8/12 | 路口 16、11 正常 |
| 4 | 1.5 倍压力分析 | 8/13 | 改进百分比数据 |
| 5 | 参数敏感性分析 | 8/14 | threshold + alpha 对比表 |

## 协作对接

- 与 **TL** 确认是否保留 EWMA 及最终参数。
- 向 **EX** 提供敏感性分析跑批需求，向 **DA** 提供 EWMA 公式与效果图素材。
