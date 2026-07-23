# engine/

## 模块职责

仿真引擎层，负责 SUMO 生命周期管理、TraCI 数据读写、每步仿真状态与指标采集。是算法层与 SUMO 之间的唯一桥接。

## 当前完成情况

- [x] `traci_bridge.py`：`TraCIBridge` 类，负责启动 SUMO、读取联合状态、写入控制动作。支持 `additional_files` 透传（2026-07-23 修复）。
- [x] `mock_bridge.py`：`MockBridge` 类，与 TraCIBridge 接口一致的离线替代，用于无 SUMO 环境。
- [x] `runner.py`：`SimulationRunner` 类，负责单次仿真的完整生命周期（启动 → 逐步运行 → 算法决策 → 采集指标 → 关闭）。支持通过 `bridge` 参数注入 MockBridge；优先使用 `configs/` 增强版配置（2026-07-23）。
- [x] `collector.py`：`MetricsCollector` 类，按固定间隔将 `JointState` 和指标写入 CSV。
- [x] `configs/`：增强版 sumocfg ×20（IA 生成），引用只读原始数据，含 tripinfo/fcd/summary 输出与 GUI 自动播放设置；20/20 通过 3600 步全量验证（`docs/batch_validate_report.md`）。

## 待完成情况

- [ ] `traci_bridge.py`：完善车道 ID 到方向（north/south/east/west）的映射；精确读取行程时间（`travelTime`）和燃油消耗（`fuel`）。
- [ ] `runner.py`：支持按流量变体替换 `.flow.xml` 后运行；支持异常中断恢复。
- [ ] `collector.py`：根据 ML 训练需求调整 CSV 列（如增加 `vehicles_json`、`signals_json` 等）。

## 需求分析

| 需求 | 说明 |
|------|------|
| SUMO 生命周期封装 | 算法层无需关心 `traci.start`/`traci.close` 细节 |
| 实时状态读取 | 每步提供排队长度、流量、当前相位等联合状态 |
| 控制指令写入 | 支持设置信号灯相位、相位时长、切换程序 |
| CSV 输出 | 为 ML 训练和实验分析提供标准化数据 |

## 关键文件

| 文件 | 说明 |
|------|------|
| `traci_bridge.py` | TraCI 批量读写桥接 |
| `mock_bridge.py` | 离线 Mock 桥接（无 SUMO） |
| `runner.py` | 单次仿真实验运行器 |
| `collector.py` | 仿真数据采集器 |
| `configs/` | 增强版 sumocfg ×20（由 `scripts/generate_configs.py` 生成，勿手改） |

## 对外接口

```python
from engine.runner import SimulationRunner
from engine.mock_bridge import MockBridge
from scenes.registry import SceneRegistry

scene = SceneRegistry().get_scene("1")

# SUMO 模式
runner = SimulationRunner(scene, algorithm)
runner.run(steps=3600)

# Mock 模式（无 SUMO）
bridge = MockBridge(tls_id="tls_0", directions=["E0", "E1", "E2", "E3"])
runner = SimulationRunner(scene, algorithm, bridge=bridge)
runner.run(steps=10)
```

## 负责人

- IB（仿真基础设施 B）：SumoSimulator 封装、TraCI 接口、云-边-端消息流
- IA（仿真基础设施 A）：配合校验 SUMO 文件可用性
