# Core

## 模块职责

`core/` 定义跨模块共享的数据契约和配置访问方式，是场景、引擎、算法、云端、API 和实验代码的基础依赖。

## 文件索引

| 文件 | 作用 |
| --- | --- |
| `types.py` | 场景、队列、车辆、联合状态、动作、预测和指标数据类 |
| `config.py` | YAML 加载、点号键访问和仓库相对路径解析 |

## 对外接口

```python
from core.config import get_config
from core.types import ControlAction, JointState, QueueState, SceneMeta

config = get_config()
output_root = config.path("paths.output_root")
```

`JointState` 是算法与云端策略的主要输入，`ControlAction` 是控制器输出，`SimulationMetrics` 是采集与实验输出契约。

## 输入与输出

- `Config` 输入 `config/default.yaml` 或首次实例化时提供的 YAML 路径。
- `Config.get()` 输出配置值，`Config.path()` 输出规范化绝对路径。
- 数据类只承载状态，不执行 I/O；字段定义见 `docs/architecture/interface.md`。

## 依赖

- `config.py` 依赖 PyYAML。
- `types.py` 仅依赖 Python 标准库。

## 已知限制

- `QueueState.capacity=0` 表示未知，消费者必须避免除零或提供退化策略。
- `arrival_history` 是每步进入路网车辆数列表，不区分进口方向。
- 数据类没有运行时 schema 校验或序列化层；API 需要自行转换。
- `Config` 单例不会自动检测磁盘配置变化。
