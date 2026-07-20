# W2 任务书：算法 B（AB）

> 周期：7/27（周日）- 8/2（周六）
> 核心目标：完善 CA-MP 多路口适配、接入云-边-端消息流、验证创新点效果

---

## 每日任务

### Day 1（7/27 周日）

1. 修复 W1 联调中发现的 CA-MP bug
2. 确认 `_parse_network()` 能正确解析不同路口的 tlLogic：
   - 路口 1：6 相位（含 2 个黄灯）
   - 路口 16：可能更多相位（5 进口道）
   - 路口 11：相位结构可能不同
3. 在路口 1 上重新验证：CA-MP 行程时间 < FixedTime

### Day 2（7/28 周一）

1. 适配 0.1s 步长路口：
   - 决策频率调整：每 10 步（= 1s）做一次决策
   ```python
   def update(self, status: EdgeStatus) -> None:
       self._status = status
       self._step_count += 1
       # 0.1s 步长路口每 10 步决策一次
       if self._timestep < 1.0 and self._step_count % 10 != 0:
           self._should_decide = False
       else:
           self._should_decide = True

   def decide(self) -> SignalAction:
       if not self._should_decide:
           return SignalAction(next_phase=self._current_phase, duration=-1.0)
       # 正常决策逻辑...
   ```
2. 在路口 11（0.1s）和路口 16（5 进口道）上测试
3. 确认溢出门控在路口 16 的 24m 短边上触发

### Day 3（7/29 周二）

1. 正式接入云-边-端消息流：
   - 确认 `on_cloud_command()` 能正确接收 CloudCoordinator 的参数
   - 验证：云端下发 min_green/max_green/base_green 后，CA-MP 行为变化
2. 测试完整消息流：
   ```
   V2XMessage → EdgeNode.on_v2x_receive()
   → EdgeNode.decide() → CAMaxPressureController.decide()
   → SignalAction → simulator.apply_signal()
   → EdgeStatus → CloudCoordinator.on_status_receive()
   → CloudCommand → CAMaxPressureController.on_cloud_command()
   ```
3. 记录消息流是否完整闭环

### Day 4（7/30 周三）

1. 在路口 1 上做三种算法的正式对比：
   - FixedTime / Actuated / CA-MP
   - 每种跑 3 次（seed=42, 123, 456）
   - 记录指标：avg_travel_time, avg_queue, throughput, fuel
2. 制作简单对比表（发给 DA 和 EX）：

| 算法 | 平均行程时间 | 平均排队 | 吞吐量 | 油耗 |
|------|-------------|---------|--------|------|
| FixedTime | ? | ? | ? | ? |
| Actuated | ? | ? | ? | ? |
| CA-MP | ? | ? | ? | ? |

3. 验证 CA-MP 在所有指标上优于或等于两个基线

### Day 5（7/31 周四）

1. 在路口 16 上做重点对比：
   - 这是演示视频的主角路口
   - 特别记录：溢出门控触发次数、短边排队变化
   - 如果 CA-MP 在路口 16 上效果显著（行程时间降低 > 15%），记录为视频素材
2. 调整溢出门控阈值（如果 0.9 不合适）：
   - 太低：频繁触发，退化为"一直给某个方向绿灯"
   - 太高：很少触发，失去保护意义
   - 在 0.8 ~ 0.95 之间测试

### Day 6（8/1 周五）

1. 协助 TL 做 W2 集成验证
2. 确保 CA-MP 在 5 个代表性路口上无崩溃
3. 提交代码给 TL

### Day 7（8/2 周六）

1. Buffer：修复遗留问题
2. 开始设计 EWMA 预测模块（W4 实现）：
   - 确定输入：过去 N 个周期各进口道的到达车辆数
   - 确定输出：下一周期预测到达量
   - 确定融入方式：`adjusted_pressure = (queue + predicted * look_ahead) / capacity`
   - 写设计笔记到 `docs/ewma_design.md`

---

## 交付物清单

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | CA-MP 0.1s 步长适配 | 7/28 | 路口 11 正常 |
| 2 | CA-MP 5 进口道适配 | 7/28 | 路口 16 正常 |
| 3 | 云-边-端消息流闭环 | 7/29 | CloudCommand 影响 CA-MP 行为 |
| 4 | 路口 1 三算法对比数据 | 7/30 | CA-MP 优于基线 |
| 5 | 路口 16 重点对比 | 7/31 | 溢出门控触发、效果显著 |
| 6 | `docs/ewma_design.md` | 8/2 | EWMA 设计笔记 |
