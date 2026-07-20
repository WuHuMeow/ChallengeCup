# W2 任务书：仿真基础设施 B（IB）

> 周期：7/27（周日）- 8/2（周六）
> 核心目标：完善云-边-端消息流、为 experiments/runner.py 添加实验参数、确保输出完整

---

## 每日任务

### Day 1（7/27 周日）

1. 为 experiments/runner.py 添加 EX 需要的命令行参数：
   ```python
   parser.add_argument("--seed", type=int, default=42)
   parser.add_argument("--flow-multiplier", type=float, default=1.0)
   parser.add_argument("--output-dir", type=str, default=None)
   ```
2. 实现 `--seed`：在 traci.start() 时传入 `["--seed", str(seed)]`
3. 实现 `--flow-multiplier`：
   - 方案 A：运行前用脚本生成临时 flow.xml（与 EX 的 scale_flow.py 配合）
   - 方案 B：通过 TraCI 动态调整（`traci.route.getIDList()` + 修改流量）
   - 推荐方案 A（更简单可靠）
4. 实现 `--output-dir`：将 tripinfo.xml/stats.xml/traj.xml 输出到指定目录

### Day 2（7/28 周一）

1. 完善 CloudPolicy 逻辑：
   - 实现基于流量的动态参数调整：
     ```python
     def _compute_params(self, states: list[JointState]) -> dict:
         """根据各路口平均排队压力调整绿灯参数"""
         avg_pressure = np.mean([np.mean([q.queue_length for q in s.queues]) for s in states])
         if avg_pressure > 0.7:  # 高压力
             return {"min_green": 15, "max_green": 80, "base_green": 40}
         elif avg_pressure > 0.4:  # 中压力
             return {"min_green": 10, "max_green": 60, "base_green": 30}
         else:  # 低压力
             return {"min_green": 8, "max_green": 45, "base_green": 25}
     ```
   - 每 60 步（或可配置间隔）通过 CloudPolicy.predict() 下发一次预测结果
2. 验证：CA-MP 在 __init__ 中通过 CloudPolicy 接收并更新参数

### Day 3（7/29 周二）

1. 完善 edge 侧的 V2X 消息过滤（已融入 JointState）：
   - 只保留属于本路口进口道的 JointState 字段
   - 模拟通信延迟（可选）：状态延迟 1-2 步到达
   ```python
   def on_state_receive(self, states: list[JointState]) -> None:
       # 过滤：只保留本路口进口道上的车辆
       relevant = [s for s in states if self._is_relevant(s)]
       # 模拟延迟：加入延迟队列
       self._delay_buffer.extend(relevant)
       # 取出上一轮的状态（模拟 1 步延迟）
       self._last_states = self._delay_buffer[:-len(relevant)] if len(self._delay_buffer) > len(relevant) else []
   ```
2. 这个延迟模拟是"通信模拟模块"的加分项（PDF 原文："模拟 V2X 消息的发送、接收、简单延迟"）

### Day 4（7/30 周三）

1. 与 EX 联调 experiments/runner.py：
   - 确认 experiments/runner.py 的所有参数正确工作
   - 确认输出文件（tripinfo.xml/stats.xml/traj.xml）在 --output-dir 下正确生成
   - 跑一次完整的单次实验验证
2. 修复联调中发现的 bug

### Day 5（7/31 周四）

1. 添加仿真运行日志：
   - 在 engine/runner.py 中记录每步的：时间、当前相位、各进口道排队、压力值
   - 输出为 CSV：`{output_dir}/simulation_log.csv`
   - 这个日志后续 DB 做可视化动画时用
2. 日志格式：
   ```csv
   step,time,phase,queue_E,queue_W,queue_N,queue_S,pressure_E,pressure_W,pressure_N,pressure_S
   0,0.0,0,5,3,8,2,0.62,0.38,1.0,0.25
   1,1.0,0,6,3,7,2,0.75,0.38,0.88,0.25
   ```

### Day 6（8/1 周五）

1. 协助 TL 做 W2 集成验证
2. 确保三种算法在路口 1 和路口 16 上都能正确输出日志
3. 提交代码给 TL

### Day 7（8/2 周六）

1. Buffer：修复遗留问题
2. 开始编写 `docs/deployment.md` 初稿（W4 完善）：
   - 环境要求（Python 版本、SUMO 版本、依赖包）
   - 安装步骤
   - 运行命令示例
   - Docker 部署（占位，W4 补充）

---

## 交付物清单

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | experiments/runner.py 新增参数 | 7/27 | --seed/--flow-multiplier/--output-dir 可用 |
| 2 | CloudPolicy 动态参数 | 7/28 | 根据压力自动调整 min/max/base_green |
| 3 | V2X 延迟模拟 | 7/29 | 状态有 1 步延迟 |
| 4 | experiments/runner.py 联调通过 | 7/30 | 单次实验输出完整 |
| 5 | simulation_log.csv 输出 | 7/31 | 每步记录相位/排队/压力 |
| 6 | `docs/deployment.md` 初稿 | 8/2 | 基本安装运行说明 |
