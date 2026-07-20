# W4 任务书：算法 B（AB）

> 周期：8/10（周日）- 8/16（周六）
> 核心目标：实现 EWMA 流量预测并接入 CA-MP、分析 1.5 倍压力测试结果

---

## 每日任务

### Day 1（8/10 周日）
1. 实现 EWMA 预测模块：
   ```python
   # algorithms/ewma_predictor.py
   class EWMAPredictor:
       """指数加权移动平均流量预测"""
       def __init__(self, alpha: float = 0.4, history_window: int = 3):
           self.alpha = alpha
           self.history_window = history_window
           self._history: dict[str, list[float]] = {}  # lane_id -> [arrival counts]
           self._predictions: dict[str, float] = {}

       def update(self, arrivals: dict[str, int]) -> None:
           """每周期更新一次（不是每步）"""
           for lane_id, count in arrivals.items():
               if lane_id not in self._history:
                   self._history[lane_id] = []
               self._history[lane_id].append(count)
               if len(self._history[lane_id]) > self.history_window:
                   self._history[lane_id].pop(0)
               # EWMA 预测
               if lane_id in self._predictions:
                   self._predictions[lane_id] = (
                       self.alpha * count + (1 - self.alpha) * self._predictions[lane_id]
                   )
               else:
                   self._predictions[lane_id] = float(count)

       def predict(self, lane_id: str) -> float:
           return self._predictions.get(lane_id, 0.0)
   ```
2. 在 CA-MP 中接入：
   ```python
   # 在 _compute_normalized_pressures() 中：
   predicted = self.predictor.predict(lane_id)
   adjusted_queue = queue + predicted * self.look_ahead  # look_ahead = 1
   norm_pressure = adjusted_queue / capacity
   ```

### Day 2（8/11 周一）
1. 在路口 1 上验证 EWMA 效果：
   - 对比有/无 EWMA 的 CA-MP
   - 预期：EWMA 在流量波动时表现更好（提前切换相位）
2. 如果效果不明显或引入不稳定，调整 alpha 值（0.2-0.6 之间测试）
3. 与 TL 确认：是否保留 EWMA

### Day 3（8/12 周二）
1. 在路口 16 上验证 EWMA：
   - 短边路口流量波动大，EWMA 应该有明显效果
2. 在路口 11（0.1s 步长）上验证：
   - 确认 EWMA 更新频率正确（每周期更新，不是每 0.1s）
3. 修复兼容性问题

### Day 4（8/13 周三）
1. 1.5 倍压力测试完成后，分析 CA-MP（含 EWMA）的表现：
   - 高压力下 EWMA 预测是否更准确（流量大、规律性强）
   - 计算 1.5 倍流量下的改进百分比
2. 与 W3 原始流量结果对比：高压力下优势是否更大

### Day 5（8/14 周四）
1. 参数敏感性分析（为报告准备）：
   - overflow_threshold: 0.8 / 0.85 / 0.9 / 0.95 的效果对比
   - EWMA alpha: 0.2 / 0.3 / 0.4 / 0.5 / 0.6 的效果对比
   - 在路口 1 和路口 16 上各跑一组
2. 记录结果，发给 EX 和 DA

### Day 6（8/15 周五）
1. 最终代码整理：
   - 确保 EWMA 模块有完整 docstring
   - 确保参数可通过 CloudPolicy 动态调整
   - 确保无 EWMA 时 CA-MP 退化为 W3 版本（向后兼容）
2. 提交代码给 TL

### Day 7（8/16 周六）
1. Buffer：修复遗留问题
2. 为 DA 准备"算法原理"章节的 EWMA 部分素材（公式 + 效果图）

---

## 交付物清单

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | `algorithms/ewma_predictor.py` | 8/10 | EWMA 预测模块完整 |
| 2 | CA-MP 接入 EWMA | 8/11 | 路口 1 效果不退化 |
| 3 | 多路口 EWMA 验证 | 8/12 | 路口 16、11 正常 |
| 4 | 1.5 倍压力分析 | 8/13 | 改进百分比数据 |
| 5 | 参数敏感性分析 | 8/14 | threshold + alpha 对比 |
