# W3 任务书：仿真基础设施 B（IB）

> 周期：8/3（周日）- 8/9（周六）
> 核心目标：保障 experiments/runner.py 稳定运行、完善日志输出、协助实验

---

## 每日任务

### Day 1（8/3 周日）
1. 监控 experiments/runner.py 在全量实验中的稳定性
2. 处理可能的 TraCI 连接断开问题（长时间运行）
3. 添加异常处理：如果 TraCI 断开，自动重连或优雅退出

### Day 2（8/4 周一）
1. 完善 simulation_log.csv 输出：
   - 确认所有 20 路口的日志格式一致
   - 添加溢出门控触发记录（每次触发记一行）
   ```csv
   step,time,event,detail
   150,150.0,overflow_gate,"lane=-E2.41, occupancy=0.92, forced_phase=2"
   ```
2. 这个日志后续 DA 写报告、DB 做可视化都要用

### Day 3（8/5 周二）
1. 协助 EX 处理 experiments/runner.py 运行中的问题
2. 如果某些路口运行时间过长，优化 engine/traci_bridge.py：
   - 减少不必要的 TraCI 调用（如不需要每步都获取所有车辆位置）
   - 对于非 GUI 模式，跳过 JointState 中车端字段的逐车采集（直接用 get_state()）

### Day 4（8/6 周三）
1. 确认所有实验的 simulation_log.csv 正确生成
2. 抽查 5 个路口的日志：相位切换是否合理、溢出门控是否记录

### Day 5（8/7 周四）
1. 开始编写 `docs/deployment.md` 完善版：
   - 完整安装步骤（Windows/Linux）
   - 环境变量配置
   - 运行命令示例（单路口、批量）
   - 输出文件说明
   - Docker 部署（与 IA 协调）
2. 这是 PDF 硬性要求的"详细的部署运行说明文档"

### Day 6（8/8 周五）
1. 协助 TL 做 W3 集成验证
2. 确保代码可复现：任何人 clone 仓库后按 deployment.md 能跑通

### Day 7（8/9 周六）
1. Buffer：修复遗留问题
2. 提交代码给 TL

---

## 交付物清单

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | TraCI 异常处理 | 8/3 | 长时间运行不崩溃 |
| 2 | 溢出门控日志 | 8/4 | 触发事件有记录 |
| 3 | 性能优化（如需要） | 8/5 | 0.1s 路口运行时间可接受 |
| 4 | `docs/deployment.md` 完善版 | 8/7 | 完整部署指南 |
