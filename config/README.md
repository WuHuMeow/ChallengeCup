# config/

## 模块职责

存放项目全局配置文件，包括数据路径、SUMO 参数、算法参数、指标采集间隔等。

## 当前完成情况

- [x] `default.yaml`：已包含项目信息、路径配置、SUMO 参数、场景流量等级、算法参数、指标采集间隔、日志格式。

## 待完成情况

- [ ] 根据实验需要增加 `test.yaml` 或 `prod.yaml` 等多环境配置。
- [ ] 根据算法调参进展更新 `algorithms.*` 参数。

## 需求分析

| 需求 | 说明 |
|------|------|
| 路径可配置 | 数据根目录、输出目录可集中修改 |
| 算法参数可配置 | 固定配时、感应控制、CA-MP 的参数集中管理 |
| 环境变量覆盖 | 支持 `CC_DATA_ROOT` 等环境变量临时覆盖 |

## 关键文件

| 文件 | 说明 |
|------|------|
| `default.yaml` | 默认全局配置 |

## 当前配置说明

```yaml
paths.data_root: "./data/intersection_data"   # 20 个路口数据目录
sumo.binary: "sumo"                           # 批量跑批用命令行版
scene.default_traffic_levels: {normal:1.0, high:1.5}  # 原始 + 1.5 倍压力
algorithms.fixed_time.use_excel_timing: false # 是否使用 Excel 配时
```

## 负责人

- TL：维护配置结构，其他人按模块读取对应参数。
