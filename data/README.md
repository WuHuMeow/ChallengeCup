# data/

## 模块职责

存放项目使用的数据集，包括 20 个雄安路口原始数据及其压缩包。

## 当前完成情况

- [x] `intersection_data/`：20 个路口原始数据，每个路口包含 SUMO 工程、流量与配时 Excel、高精地图 PNG。
- [x] `intersection_data.zip`：上述数据的完整压缩包（66.7 MB）。

## 待完成情况

- [ ] 根据实验进展生成流量变体输出（可选，也可输出到 `output/variants/`）。
- [ ] 如需减小仓库体积，可考虑使用 Git LFS 管理 `intersection_data.zip`。

## 需求分析

| 需求 | 说明 |
|------|------|
| 数据完整性 | 20 个路口全部随仓库提交，避免队员本地路径不一致 |
| 离线可用 | 压缩包便于无 Git 环境时传输 |
| 命名兼容 | 路口 11 的地图目录为 `高清地图`，其余为 `高精地图`，代码层已做兼容 |

## 数据结构

```text
intersection_data/{id}/
├── sumo工程/
│   ├── demo_{id}.sumocfg
│   ├── demo_{id}.net.xml
│   ├── demo_{id}.rou.xml
│   ├── demo_{id}.flow.xml
│   └── demo_{id}.turn.xml
├── 路口数据/
│   └── demo_{id}流量和交叉口配时方案.xlsx
└── 高精地图/          # 路口 11 为 "高清地图"
    └── demo_{id}.png
```

## 关键文件

| 文件 | 说明 |
|------|------|
| `intersection_data/` | 20 个路口原始数据 |
| `intersection_data.zip` | 数据压缩包 |

## 负责人

- IA（仿真基础设施 A）：维护数据组织方式
- IB（仿真基础设施 B）：配合确认 SUMO 文件可用性
