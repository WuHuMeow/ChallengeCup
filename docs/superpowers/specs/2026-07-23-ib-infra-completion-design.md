# IB（仿真基础设施 B）全量补齐设计

> 日期：2026-07-23 | 角色：IB | 范围：docs/team/tasks/w1-w6/ib-infrastructure-b.md 全部可执行项
> 前置调查：2026-07-23 只读盘点（31 个测试全过；SUMO 1.27.1 环境就绪；路口 1 固定配时已实证跑通）

## 一、背景与现状

IB 职责：TraCIBridge 封装、SimulationRunner 主循环、CloudPolicy 云-边-端消息流、experiments 批量入口、deployment/interface 文档。

现状（证据见调查记录）：

- **已完成**：TraCIBridge 基础版（get_state/apply_actions/start/close）、SimulationRunner 主循环（含 try/finally + MockBridge 注入）、MetricsCollector、CloudPolicy 骨架（EWMA predict + dispatch_base_green 桩）、examples/run_fixed_time.py（实证跑通）、SceneRegistry/VariantGenerator 接入良好。
- **缺口**：W1 收尾（get_lane_capacity、edge_mapping 进口道筛选、run_ca_max_pressure 示例）；W2 全部（CLI 三参数、真 seed、压力分档、EdgeChannel、simulation_log）；W3 全部（FatalTraCIError 韧性、events.csv、日志审计）；W4 全部（vehicle_sample_rate、vehicles 上限、arrival_history、极高压力档、压力实测）；W5/W6（清理、lint、文档一致性、验证文档）。
- **注意**：deployment.md / Docker / scripts / edge_mapping / batch_validate 均为 IA（peng）交付，不计为 IB 工作量。

## 二、设计原则

1. **向后兼容**：7/23 接口已冻结，所有变更只新增可选字段/参数（带默认值），不修改现有签名语义。
2. **机制先行**：依赖 AB 算法侧的项（溢出门控 events、EWMA 深度接入）由 IB 建好机制与钩子，算法实现归 AB。
3. **YAGNI**：TraCI 订阅批量读取优化跳过——IA 实测 20 路口 3600 步合计 59s，性能不是瓶颈，在此记录决策理由。
4. **每项带实证**：pytest、真实 SUMO 仿真、压力实测、lint，不接受"理论上能跑"。

## 三、分阶段设计

### 阶段 1：W1 收尾

- `engine/traci_bridge.py` 新增 `get_lane_capacity(lane_id) -> float`：车道长度 / 7.5m（5m 车长 + 2.5m 间距），注释说明系数来源。
- 进口道筛选：`scripts/data/generate_edge_mapping.py` 支持输出结构化 JSON（存 `data/intersection_data/metadata/edge_mapping.json`）；TraCIBridge 加载它区分进口/出口车道，加载失败回退现有 `getControlledLanes` 行为（保证 Mock 与旧场景不受影响）。
- 新增 `examples/run_ca_max_pressure.py`：仿 run_fixed_time.py 结构，接 CAMaxPressureAlgorithm（当前为 MVI 桩，足以验证管道贯通）。
- **实证**：`python examples/run_ca_max_pressure.py 1 3600` 退出码 0，输出 CSV 的 queue 列有非零值；`pytest` 全过。

### 阶段 2：W2 实验入口与云-边-端

- `experiments/runner.py` 补 argparse CLI：`--seed`（默认 42）、`--flow-multiplier`（默认 1.0，任意浮点）、`--output-dir`、`--intersection`、`--steps`（默认 3600）、`--algorithm`（fixed_time/actuated/ca_maxpressure）。`--help` 自检说明清晰。
- **真 seed**：TraCIBridge.start 增加 `seed` 参数，`traci.start` 命令追加 `--seed`；experiments 链路全程透传。实证：同 seed 两次运行 CSV 一致，异 seed 有差异。
- **任意流量倍率**：扩展 `scenes/variant.py` 支持任意 multiplier（复用现有 flow.xml 缩放机制），不新造 scale_flow.py 脚本。倍率 1.0 时直接用原始 flow。
- `cloud/cloud_policy.py` 实现 `_compute_params(states)` 压力分档：avg_pressure > 0.8 激进档（min_green=20）、> 0.4 中档、其余常规档；每 60 步周期下发；下发时打日志（step/avg_pressure/params）。
- 新增 `engine/edge_channel.py`：EdgeChannel 实现 V2X 消息过滤 + 1 步延迟模拟（PDF 加分项），附单测。
- runner 支持可选 `simulation_log.csv`：每步记录 step/time/phase/queue/pressure 列。
- **实证**：`python experiments/runner.py --help` 正常；路口 1 带 seed/倍率/output-dir 跑一次真实仿真；新增单测全过。

### 阶段 3：W3 运行韧性

- `engine/traci_bridge.py`：`tick()` 捕获 `FatalTraCIError`，打印 "closing gracefully" 并优雅退出（返回 False）；可选自动重连（`max_restarts` 参数，默认 0=不重连）；`close()` 幂等。
- runner 层确认 `try/finally` 保证 `bridge.close()` 一定调用（现有已具备，回归验证）。
- **实证**：仿真运行中 `taskkill //F //IM sumo.exe`，runner 无未捕获异常、退出码 0、日志含 closing gracefully。
- `engine/runner.py` 增加 `events.csv` 机制：定义事件行格式（step/type/detail），提供写入接口，CA-MP 溢出门控实现后可直接写入。
- 全量实验稳定跑一轮后撰写 `docs/reports/w3-log-audit.md`（崩溃/重连/内存记录）。

### 阶段 4：W4 高压优化与压力实测

- `core/types.py`：JointState 新增可选字段 `vehicles`（默认空列表）与 `arrival_history`（默认空 list，滚动窗口定长 300 步），同步更新 `docs/architecture/interface.md`。
- `engine/traci_bridge.py`：`vehicle_sample_rate`（默认 1=全采，3=每 3 辆取 1）；`vehicles` 500 辆硬上限（超出只保留进口道车辆）；`arrival_history` 滚动窗口。附单测。
- CloudPolicy 极高压力档并入阶段 2 的分档实现（此处验证 1.5 倍流量下参数确实切换并影响行为，日志可见）。
- **实证**：`python experiments/runner.py --intersection 1 --steps 3600 --flow-multiplier 1.5 --output-dir output/stress` 完整跑完；`tracemalloc` 峰值内存 < 1GB；输出产物齐全。

### 阶段 5：W5/W6 清理与定稿

- 代码清理：删除调试残留、TODO/FIXME 清零（engine/cloud/experiments 范围内 IB 负责文件）；docstring 补全（参数/返回/异常）。
- `scripts/quality/lint_check.sh`：`flake8 engine/ cloud/ experiments/ --max-line-length=100` + grep 调试残留检查，输出 clean。
- 文档一致性：更新 `docs/architecture/interface.md`（新增字段、消息流图、使用示例）；修正 `docs/operations/deployment.md` 中失效的 `experiments/runner.py --help` 引用。
- 撰写 `docs/reports/w5-verification.md`（验证矩阵：每项任务的验证命令与结果）；W6 review 机制文档（docs/reports/w6-review-issues.md 模板建立）。
- **实证**：`pytest` 全过；`bash scripts/quality/lint_check.sh` 输出 clean；docs 与代码字段逐条一致。

## 四、数据流（变更后）

```
SUMO <--TraCI--> TraCIBridge --JointState(+vehicles/arrival_history)--> Algorithm
                     |  ^                                                |
                     |  |--ControlAction---------------------------------+
                     |-- seed / FatalTraCIError 韧性 / 采样与上限
SimulationRunner: tick -> get_state -> algorithm.step -> apply_actions
                  -> simulation_log.csv（每步）/ events.csv（事件）/ 快照 CSV
experiments/runner.py: CLI -> run_batch(seed/倍率/output-dir 透传) -> per-run 输出目录
CloudPolicy: predict(EWMA) + _compute_params(压力三档) --每60步--> 算法参数
EdgeChannel: V2X 消息过滤 + 1步延迟（独立模块，可选挂接）
```

## 五、错误处理

- TraCI 连接失败：启动时报清晰中文错误（检查 SUMO_HOME / sumocfg 路径）——已有，保留。
- 仿真中断：FatalTraCIError → 优雅退出码 0 + 日志；可选自动重连。
- 参数非法：argparse 类型校验 + runner 对不存在路口/倍率 <= 0 显式报错。
- 文件缺失：edge_mapping.json 缺失时回退 getControlledLanes 并打 warning，不中断。

## 六、测试策略

- 新增单测：EdgeChannel 延迟/过滤、CloudPolicy 三档分档、vehicle_sample_rate 与 500 上限、arrival_history 滚动、CLI 参数解析、真 seed 透传（MockBridge 层）。
- 集成实证：路口 1 双算法 3600 步、1.5 倍压力 + tracemalloc、断线 taskkill 测试、同 seed 复现。
- 回归：现有 31 个测试必须保持全过。

## 七、明确不做（YAGNI）

- TraCI 订阅批量读取性能优化（实测无瓶颈，理由见设计原则 3）。
- 独立 scripts/scale_flow.py（复用 scenes/variant.py 扩展即可）。
- CA-MP 三项创新、EWMA 算法侧接入（归 AB，IB 只建机制）。
- Docker 镜像构建与实机一致性验证（IA 已交付 Dockerfile；实机构建属 W4 联调项，记录待回填）。
