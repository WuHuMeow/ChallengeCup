# 如何导入新路口数据

## 目的

将组委会下发的新路口 SUMO 工程导入项目，使其可被仿真引擎识别和运行。

## 前置条件

- 拥有新路口数据文件夹（含 `.net.xml`、`.rou.xml`、`.sumocfg`、配时 Excel）
- 已安装项目依赖：`pip install -e .`

## 操作步骤

1. 在 `data/intersection_data/` 下创建编号目录（如 `21/`）：

```
data/intersection_data/21/
├── sumo工程/
│   ├── demo_21.net.xml
│   ├── demo_21.rou.xml
│   ├── demo_21.flow.xml      # 可选
│   ├── demo_21.turn.xml      # 可选
│   └── demo_21.sumocfg
├── 路口数据/
│   └── demo_21流量和交叉口配时方案.xlsx
└── 高精地图/
    └── demo_21.png           # 可选
```

2. 确保文件命名遵循 `demo_N.*` 格式（N = 路口编号）

3. 运行元数据提取脚本：
```bash
python scripts/extract_metadata.py
```
这会更新 `data/intersection_data/metadata/intersections.yaml`。

4. 生成边方向映射：
```bash
python scripts/generate_edge_mapping.py
```
这会更新 `data/intersection_data/metadata/edge_mapping.json` 和 `docs/edge_mapping.md`。

5. 生成增强版仿真配置：
```bash
python scripts/generate_configs.py
```
这会在 `engine/configs/` 下生成 `demo_21.sumocfg`。

6. 验证新路口可运行：
```bash
python scripts/validate_all.py 21
```

## 示例

导入路口 21 后运行 CA-MP 仿真：
```bash
python examples/run_ca_max_pressure.py 21 3600
```

## 常见问题

**Q: 目录名必须是 `高精地图` 吗？**
A: 是的。路口 11 使用了 `高清地图`（历史原因），代码中有兼容处理（`scenes/registry.py`），但新路口请统一用 `高精地图`。

**Q: 没有 Excel 配时文件怎么办？**
A: 可以没有。`config/default.yaml` 中 `use_excel_timing: false` 时使用 SUMO 路网自带配时。

**Q: validate 报 FAIL？**
A: 检查 `.net.xml` 的 SUMO 版本兼容性（需 net format >= 1.20），参见 `docs/migration_log.md`。
