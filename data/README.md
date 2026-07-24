# Data

## 模块职责

`data/` 保存项目随仓库分发的 20 个雄安路口原始 SUMO 工程、流量/配时 Excel、地图图片及其元数据。原始路口文件作为只读输入使用，运行产物写入 `output/`。

## 文件索引

| 路径 | 作用 |
| --- | --- |
| `intersection_data/{1..20}/` | 每个路口的 SUMO 工程、流量与配时文件、地图 PNG |
| `intersection_data/metadata/intersections.yaml` | 由 `scripts/data/extract_metadata.py` 生成的路口元数据 |
| `intersection_data/metadata/edge_mapping.json` | 由边映射脚本生成的结构化边方向数据 |
| `intersection_data.zip` | 路口数据的离线传输压缩包 |

单个路口的目录结构：

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
└── 高精地图/          # 路口 11 使用“高清地图”
    └── demo_{id}.png
```

## 接口与命令

从仓库根目录更新元数据或边方向映射：

```powershell
python scripts/data/extract_metadata.py
python scripts/data/generate_edge_mapping.py
```

场景代码通过 `SceneRegistry` 读取本目录；可用 `CC_DATA_ROOT` 指向仓库外的同构数据根目录：

```powershell
$env:CC_DATA_ROOT = "D:\data\intersection_data"
```

## 输入与输出

- 输入：路口 ID 目录中的 `.sumocfg`、`.net.xml`、`.rou.xml`、`.flow.xml`、`.turn.xml`、配时 `.xlsx` 和地图 `.png`。
- 元数据脚本输出 `metadata/intersections.yaml`；边映射脚本输出 `metadata/edge_mapping.json` 和 `docs/reference/edge-mapping.md`。
- `scenes.VariantGenerator` 根据基准 `.flow.xml` 在 `output/variants/` 生成倍率变体，不覆盖原始文件。

## 依赖

- 场景发现依赖 `core.config`、`scenes.registry` 和本地文件系统。
- 元数据提取依赖 PyYAML；边映射生成依赖 `sumolib`（从 SUMO 路网读取边信息）。
- 真实仿真还需要 SUMO 读取路口工程。

## 已知限制

- `SceneRegistry` 要求数字路口目录、固定中文子目录和 `demo_{id}` 文件命名；缺失必要文件的路口会被跳过。
- 路口 11 的地图目录名是“高清地图”，代码已兼容；其他命名变体不会自动推断。
- 元数据与边映射脚本会覆盖生成文件；修改来源数据后应重新运行脚本并复核 diff。
- 流量变体只缩放 XML 中的 `<flow number>`，不会处理 `probability` 或 `vehsPerHour`。
- 压缩包便于离线传输，但仓库不保证压缩包与目录内容在每次手工修改后自动同步。
