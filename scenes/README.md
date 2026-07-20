# scenes/

## 模块职责

场景管理层，负责 20 个路口数据的统一注册、索引、变体生成、Excel 配时读取，以及场景校验和扰动事件注入。

## 当前完成情况

- [x] `registry.py`：`SceneRegistry` 自动发现 20 个路口，输出 `SceneMeta`，兼容 `高精地图`/`高清地图` 命名差异。
- [x] `variant.py`：`VariantGenerator` 支持生成 0.5x / 1.0x / 3.0x 流量变体。
- [x] `timing_loader.py`：从 Excel 读取信号配时方案，输出 `TimingPlan`。
- [ ] `validator.py`：尚未实现。
- [ ] `perturbation.py`：尚未实现。
- [ ] `osm_importer.py`：尚未实现（可扩展接口）。

## 待完成情况

- [ ] `validator.py`：实现无算法仿真校验，检测死锁、未完成任务车辆比例。
- [ ] `perturbation.py`：实现施工占道（关闭车道）、大型活动（临时 OD 流量）、学校高峰等扰动事件注入。
- [ ] `osm_importer.py`：可选实现 OSM / 规划图纸路网导入骨架。

## 需求分析

| 需求 | 说明 |
|------|------|
| 统一索引 | 20 个路口分散在不同目录，需要统一入口 |
| 变体生成 | 支持 60 个场景（20 路口 × 3 流量等级）用于 180 次仿真 |
| 配时读取 | 固定配时基线需读取 Excel 配时方案 |
| 扰动注入 | PDF 功能二要求支持施工占道、大型活动等扰动 |
| 场景校验 | 跑批前需确认场景不会死锁 |

## 关键文件

| 文件 | 说明 |
|------|------|
| `registry.py` | 20 路口元数据索引 |
| `variant.py` | 流量变体生成 |
| `timing_loader.py` | Excel 配时读取 |
| `validator.py` | 场景校验（待实现） |
| `perturbation.py` | 扰动事件注入（待实现） |

## 对外接口

```python
from scenes.registry import SceneRegistry
from scenes.variant import VariantGenerator, TrafficLevel

registry = SceneRegistry()
scene = registry.get_scene("1")

vg = VariantGenerator()
flow_file = vg.generate(scene.meta, TrafficLevel.HIGH, output_dir)
```

## 负责人

- IA（仿真基础设施 A）：SUMO 版本统一、20 路口迁移验证
- IB（仿真基础设施 B）：配合校验
