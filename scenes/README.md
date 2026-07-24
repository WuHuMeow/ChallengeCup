# Scenes

## 模块职责

`scenes/` 将 20 个路口工程注册为统一 `Scene`，读取 Excel 信号配时，并生成不修改原始数据的流量 XML 变体。

## 文件索引

| 文件 | 作用 |
| --- | --- |
| `registry.py` | 扫描数字路口目录并构建 `SceneMeta` |
| `variant.py` | 缩放 flow 数量并重命名 vType/flow ID，避免重复定义 |
| `timing_loader.py` | 解析 Excel 配时工作表为 `TimingPlan` |

## 对外接口

```python
from core.types import TrafficLevel
from scenes.registry import SceneRegistry
from scenes.variant import VariantGenerator

registry = SceneRegistry()
scene = registry.get_scene("1")
variant = VariantGenerator().generate(scene.meta, TrafficLevel.HIGH, output_dir)
```

`parse_timing_excel(path)` 返回时段名称到 `TimingPlan` 的映射。

## 输入与输出

- 输入：`data/intersection_data/{id}/` 下的 SUMO XML、流量/配时 Excel 和可选地图 PNG。
- `SceneRegistry` 输出 `SceneMeta` 或 `Scene`。
- `VariantGenerator` 输出新的 `.flow.xml`，不覆盖原始 flow 文件。
- 配时加载器输出内存中的 `TimingPlan`。

## 依赖

- 依赖 `core.config`、`core.types`、pandas 和 Python XML 标准库。
- 默认数据根目录来自 `config/default.yaml`，可由 `CC_DATA_ROOT` 覆盖。

## 已知限制

- 注册表只扫描名称为数字的一级目录，并要求固定的中文子目录和文件命名。
- 路口缺少 net、route、flow、sumocfg 或 Excel 任一必要文件时会被跳过。
- 变体生成只缩放 `<flow number>`；不会缩放 `probability` 或 `vehsPerHour`。
- 当前没有场景死锁验证、施工占道、活动扰动或 OSM 导入模块。
