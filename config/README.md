# Config

## 模块职责

`config/` 保存项目默认运行时配置，集中管理仓库路径、SUMO 参数、场景流量等级、算法阈值、指标采样和日志格式。

## 文件索引

| 文件 | 作用 |
| --- | --- |
| `default.yaml` | `core.config.Config` 默认加载的 YAML 配置 |

## 对外接口

```python
from core.config import get_config

config = get_config()
steps = config.get("sumo.default_simulation_steps", 3600)
data_root = config.path("paths.data_root")
```

可用环境变量覆盖路口数据根目录：

```powershell
$env:CC_DATA_ROOT = "D:\data\intersection_data"
```

## 输入与输出

- 输入：UTF-8 YAML；相对路径按仓库根目录解析。
- 输出：`Config.get()` 返回标量或嵌套对象，`Config.path()` 返回绝对 `Path`。
- 主要路径：`data/intersection_data`、`output` 和可选 `ml/model.pkl`。

## 依赖

- 配置加载依赖 PyYAML。
- 字段消费者包括 `core`、`scenes`、`engine`、`algorithms` 和 `cloud`。

## 已知限制

- `Config` 是进程级单例；首次加载后再次传入其他 YAML 路径不会重新加载。
- 仅 `CC_DATA_ROOT` 有环境变量覆盖逻辑，其他字段不能直接用环境变量覆盖。
- 配置不进行 schema 校验；拼写错误通常会在消费者读取时才暴露。
- `paths.model_path` 可以不存在，此时 `CloudPolicy` 回退到 EWMA。
