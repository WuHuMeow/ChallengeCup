# W2 任务书：算法 A（AA）

> 周期：7/27（周日）- 8/2（周六）
> 核心目标：完善感应控制算法、协助 AB 调试 CA-MP、准备多路口适配

---

## 每日任务

### Day 1（7/27 周日）

1. 修复 W1 遗留的 ActuatedController 问题（如有）
2. 在路口 1 上验证感应控制：
   - 确认绿灯时长在 min_green ~ max_green 之间动态变化
   - 确认排队低于阈值时能提前切换相位
3. 与 TL 的固定配时对比数据核对：感应控制应略优于固定配时

### Day 2（7/28 周一）

1. 适配 0.1s 步长路口（11-13、15-20）：
   - ActuatedController 中 `_green_elapsed` 的增量需要根据步长调整
   - 方案：从 sumocfg 或 net.xml 读取步长，或从 IB 的 simulator 获取
   ```python
   def update(self, status: EdgeStatus) -> None:
       # 步长从外部传入或自动检测
       self._green_elapsed += self._timestep  # 1.0 或 0.1
   ```
2. 在路口 11（0.1s 步长）上测试感应控制
3. 在路口 16（5 进口道）上测试感应控制

### Day 3（7/29 周二）

1. 协助 AB 调试 CA-MP：
   - 对比 CA-MP 与 ActuatedController 在路口 1 上的行为差异
   - 如果 CA-MP 效果不如预期，帮助排查：
     - 压力计算是否正确
     - 相位映射是否正确
     - 容量计算是否合理
2. 为 AB 提供"感应控制 vs CA-MP"的对比视角

### Day 4（7/30 周三）

1. 为 ActuatedController 添加参数可配置性：
   - min_green、max_green、extension、gap_threshold 从外部传入
   - 支持通过 CloudCommand 动态调整（与 CA-MP 一致）
   ```python
   def on_cloud_command(self, cmd: CloudCommand) -> None:
       params = cmd.strategy_params
       if "min_green" in params:
           self.min_green = params["min_green"]
       if "max_green" in params:
           self.max_green = params["max_green"]
   ```
2. 这样实验组可以统一用 CloudCoordinator 调参，三种算法公平对比

### Day 5（7/31 周四）

1. 在 5 个代表性路口上测试 ActuatedController：
   - 路口 1（标准十字、1s 步长）
   - 路口 11（0.1s 步长）
   - 路口 16（5 进口道、24m 短边）
   - 路口 5（随机选一个）
   - 路口 20（随机选一个）
2. 记录每个路口的运行状态和指标
3. 向 EX 报告：哪些路口感应控制表现异常（如果有）

### Day 6（8/1 周五）

1. 协助 TL 做 W2 集成验证
2. 确保 `--algo actuated` 在 main.py 中正确工作
3. 提交代码给 TL

### Day 7（8/2 周六）

1. Buffer：修复遗留问题
2. 开始阅读 Webster 公式（可选第三基线，如果时间允许在 W4 加入）：
   - Webster 最优周期：C₀ = (1.5L + 5) / (1 - Y)
   - 各相位绿灯：gᵢ = (C₀ - L) × yᵢ / Y
   - 记录公式，W4 决定是否实现

---

## 交付物清单

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | ActuatedController 0.1s 适配 | 7/28 | 路口 11 正常运行 |
| 2 | ActuatedController 5 进口道适配 | 7/28 | 路口 16 正常运行 |
| 3 | CloudCommand 参数接收 | 7/30 | 感应控制支持云端调参 |
| 4 | 5 路口测试报告 | 7/31 | 无崩溃、指标合理 |
