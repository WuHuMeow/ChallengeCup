# core/

## 模块职责

全项目共享的核心层，定义数据契约、配置加载和跨模块使用的通用类型。所有算法、仿真引擎、云端策略、API 层均依赖本模块。

## 当前完成情况

- [x] `types.py`：定义 `SceneMeta`、`Scene`、`JointState`、`ControlAction`、`PredictionResult`、`SimulationMetrics`、`QueueState`、`PhaseInfo`、`TimingPlan` 等核心数据类。
- [x] `config.py`：实现 YAML 配置加载，支持通过 `CC_DATA_ROOT` 环境变量覆盖数据根目录。

## 待完成情况

- [ ] 根据后续接口演进补充新的共享类型（如 `VehicleState`、`TrafficLightState` 等）。
- [ ] 如需支持多环境配置（dev/test/prod），可在 `config/` 下增加对应 YAML 文件。

## 需求分析

| 需求 | 说明 |
|------|------|
| 类型统一 | 避免各模块自行定义同名但结构不同的数据结构 |
| 配置集中 | 数据路径、SUMO 参数、算法参数统一从 YAML 读取 |
| 环境兼容 | Windows/Linux/macOS 路径解析一致 |

## 关键文件

| 文件 | 说明 |
|------|------|
| `types.py` | 核心数据契约 |
| `config.py` | 配置加载器 |

## 对外接口

```python
from core.types import JointState, ControlAction, SceneMeta
from core.config import get_config

config = get_config()
data_root = config.path("paths.data_root")
```

## 负责人

- 成员6（后端负责）统一维护接口契约，其他人按需使用。
