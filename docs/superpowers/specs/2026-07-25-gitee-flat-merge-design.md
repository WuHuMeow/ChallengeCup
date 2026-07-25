# Gitee 平铺结构合并设计

## 1. 背景与目标

当前 Gitee 仓库 `fyx0927/challenge-cup` 与本地仓库都包含项目更新，但目录布局不同：Gitee 使用 `core/`、`engine/`、`algorithms/` 等顶层平铺模块，本地使用 `ca_mp/` 命名空间包，并包含更完整的仿真增强、测试和文档。

本次工作目标是：

- 以 Gitee `master` 的顶层平铺结构作为最终仓库结构。
- 保留本地较新的算法、仿真、云端策略、测试、元数据和验证能力。
- 合并 Gitee 独有文件，避免简单覆盖造成内容丢失。
- 更新全部 Python 导入、配置路径、脚本入口、Markdown 和 README 引用。
- 完成本地验证后暂停，等待用户检查，再决定是否覆盖推送 GitHub。

## 2. 最终结构与迁移边界

本地模块迁移关系如下：

| 本地路径 | 最终路径 | 处理原则 |
|---|---|---|
| `ca_mp/core/` | `core/` | 以本地增强实现为准，保留 Gitee 独有文件 |
| `ca_mp/engine/` | `engine/` | 保留 TraCI、重连、采样、事件和边缘通道增强 |
| `ca_mp/algorithms/` | `algorithms/` | 保留本地三种控制算法实现 |
| `ca_mp/cloud/` | `cloud/` | 保留本地云端参数下发与 EWMA 能力 |
| `ca_mp/ml/` | `ml/` | 保留本地特征、训练和评估模块 |
| `ca_mp/api/` | `api/` | 保留本地 API 实现 |
| `ca_mp/experiments/` | `experiments/` | 保留本地批量实验与指标实现 |
| `ca_mp/scenes/` | `scenes/` | 保留本地场景注册、变体和配时加载 |
| `ca_mp/visualization/` | `visualization/` | 保留本地可视化实现 |

同时保留或合并以下本地内容：

- `engine/edge_channel.py`、`engine/events.py` 及增强版 SUMO 配置。
- `data/intersection_data/metadata/edge_mapping.json`。
- 本地 `tests/unit/` 与 `tests/integration/` 中的新增测试能力。
- 本地 `pyproject.toml`，并调整包发现配置以适配平铺模块。
- `output/` 运行产物目录与 Gitee `report/` 报告目录；二者职责不同，不互相覆盖。

最终代码不再以 `ca_mp/` 作为运行时主入口。所有导入统一改为 `from core...`、`from engine...`、`from algorithms...` 等平铺形式。

## 3. 代码、脚本与测试合并

同路径代码以本地增强版本为基线，再吸收 Gitee 版本中不存在于本地的内容。对于测试文件，不直接覆盖同名文件，而是逐个合并测试用例，保留 Gitee 原有覆盖范围和本地新增覆盖范围。

脚本和配置同步调整：

- `ca_mp/engine/configs/` 改为 `engine/configs/`。
- `scripts/data/`、`scripts/simulation/`、`scripts/validation/` 中的脚本按 Gitee 的 `scripts/` 入口结构整理。
- `config/default.yaml` 中的模型、数据和输出路径改为平铺结构。
- 示例、模块入口和 API 启动命令改为平铺导入。

## 4. 文档同步

以 Gitee 文档布局为主，并合并本地最新内容：

- `README.md` 和 `docs/总路线.md` 作为项目入口和路线图。
- `docs/team/tasks/` 的内容迁移并统一到 Gitee 的 `docs/tasks/` 命名结构。
- 本地架构、部署、验证和报告文档合并到 Gitee 对应文档。
- 所有模块 README、示例 README、脚本 README、测试 README 和设计文档中的路径、命令、导入示例全部更新。
- 对已过期的 `ca_mp/`、`docs/team/`、`docs/operations/`、旧脚本路径等引用进行全仓扫描和修复；本设计文档中的迁移对照表和明确标注的历史说明除外。

历史设计文档如需保留原始背景，将明确标注历史布局，并确保当前操作指引指向最终平铺路径。

## 5. 验证策略

迁移完成后按以下层次验证：

1. 使用 `pytest -q` 执行全部单元和集成测试。
2. 使用 Python 导入检查与 `compileall` 检查所有平铺模块。
3. 扫描旧路径和旧导入，确认不存在会影响当前运行的残留引用。
4. 执行仓库已有的验证脚本和输出完整性检查。
5. 在本机具备 SUMO 时执行可运行仿真验证；若缺少 SUMO 或 TraCI 依赖，单独记录环境限制，不将未执行的仿真验证标记为通过。

## 6. 交付与远程推送

本地迁移、文档更新和验证完成后，先向用户提供：

- 结构变更摘要。
- 保留和迁移的本地增强内容。
- 文档更新范围。
- 测试与验证命令及结果。
- 仍受环境限制的项目。

在用户明确检查并确认前，不推送 GitHub。确认后再将结果覆盖推送到 `WuHuMeow/ChallengeCup` 的目标分支。
