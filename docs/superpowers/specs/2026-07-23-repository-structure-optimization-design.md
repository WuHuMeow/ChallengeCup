# 仓库目录结构优化设计

> **历史迁移记录：** 下文的旧路径是来源到目标的迁移映射，用于审计目录重组；它们不是当前导航或运行命令。
>
> 日期：2026-07-23
>
> 范围：目录分类、文件迁移、README 与 Markdown 链接同步
>
> 约束：保持公共 Python 包和导入路径不变，保留当前未提交改动

## 一、目标

当前源码包规模较小，主要混乱集中在 `scripts/`、`tests/`、`docs/` 和 `output/`：

- 工具脚本按生成、仿真、验证、质量检查混放。
- 测试文件平铺，无法快速区分纯逻辑测试与跨模块测试。
- 文档导航层同时包含架构、部署、报告、任务和参考资料。
- 历史运行产物散落在 `output/` 根目录，临时检查与正式证据混杂。
- 多个模块 README 未覆盖当前文件，且进度复选框已经过期。

本次优化要让文件位置反映职责，同时避免修改 `from engine...`、`from scenes...` 等公共导入路径。

## 二、设计原则

1. **公共导入稳定**：不移动 `algorithms/`、`api/`、`cloud/`、`config/`、`core/`、`engine/`、`experiments/`、`ml/`、`scenes/`、`visualization/`。
2. **原始数据只读**：不移动或改名 `data/intersection_data/` 与 `engine/configs/`。
3. **工作流路径稳定**：不移动 `docs/superpowers/` 和 `.superpowers/sdd/`。
4. **运行输出兼容**：保留 `output/csv/`、`output/logs/`、`output/variants/` 作为默认运行接口。
5. **历史产物只迁移不删除**：现有验证、实验和检查产物全部归档。
6. **命名符合文件类型**：Python 文件继续使用 `snake_case`；Markdown 使用英文 `kebab-case`；官方赛题 PDF 保留原文件名。
7. **文档描述当前事实**：模块 README 不再维护易过期的进度复选框，进度由报告和任务书承载。

## 三、目标结构

```text
challenge-cup/
├── algorithms/                 # 源码包保持原位
├── api/
├── cloud/
├── config/
├── core/
├── engine/
├── experiments/
├── ml/
├── scenes/
├── visualization/
├── data/                       # 原始数据保持原位
├── docker/
├── examples/
├── scripts/
│   ├── data/
│   ├── simulation/
│   ├── validation/
│   ├── quality/
│   └── README.md
├── tests/
│   ├── unit/
│   ├── integration/
│   └── README.md
├── docs/
│   ├── architecture/
│   ├── operations/
│   ├── reports/
│   ├── team/
│   ├── guides/
│   ├── notes/
│   ├── reference/
│   ├── superpowers/
│   └── README.md
├── output/
│   ├── csv/                    # 当前运行结果，保持兼容
│   ├── logs/
│   ├── variants/
│   ├── archive/
│   │   ├── validation/
│   │   ├── experiments/
│   │   └── checks/
│   ├── deliverables/
│   └── README.md
└── README.md
```

## 四、文件迁移

### 4.1 scripts

| 新目录 | 文件 |
|---|---|
| `scripts/data/` | `extract_metadata.py`、`generate_edge_mapping.py` |
| `scripts/simulation/` | `generate_configs.py`、`split_jobs.py` |
| `scripts/validation/` | `validate_all.py`、`batch_validate.py`、`check_outputs.py`、`check_seed_repro.py`、`stress_memory.py` |
| `scripts/quality/` | `lint_check.sh` |

旧的 `scripts/*.py` 路径不保留包装文件。仓库内的命令和链接全部更新到新路径。

### 4.2 tests

| 新目录 | 文件 |
|---|---|
| `tests/unit/` | `test_algorithms.py`、`test_cloud.py`、`test_edge_channel.py`、`test_ml.py`、`test_mock_bridge.py`、`test_types_fields.py`、`test_vehicles.py` |
| `tests/integration/` | `test_api.py`、`test_edge_mapping.py`、`test_events.py`、`test_experiments.py`、`test_resilience.py`、`test_scenes.py`、`test_seed.py`、`test_step_log.py` |

`pytest tests/` 继续作为统一入口，迁移前后测试收集数量必须一致。

### 4.3 docs

| 旧路径 | 新路径 |
|---|---|
| `docs/interface.md` | `docs/architecture/interface.md` |
| `docs/deployment.md` | `docs/operations/deployment.md` |
| `docs/sumo_env_setup.md` | `docs/operations/sumo-environment-setup.md` |
| `docs/batch_validate_report.md` | `docs/reports/batch-validation-report.md` |
| `docs/migration_log.md` | `docs/reports/sumo-migration-log.md` |
| `docs/w3_log_audit.md` | `docs/reports/w3-log-audit.md` |
| `docs/w5_verification.md` | `docs/reports/w5-verification.md` |
| `docs/w6_review_issues.md` | `docs/reports/w6-review-issues.md` |
| `docs/总路线.md` + `docs/tasks/roadmap.md` | 合并为 `docs/team/project-roadmap.md` |
| `docs/tasks/w1/` 至 `docs/tasks/w6/` | `docs/team/tasks/w1/` 至 `docs/team/tasks/w6/` |
| `docs/edge_mapping.md` | `docs/reference/edge-mapping.md` |
| `docs/pdf/` | `docs/reference/competition/` |
| `docs/notes/docker_sumo_research.md` | `docs/notes/docker-sumo-research.md` |

`docs/guides/`、`docs/notes/` 和 `docs/superpowers/` 保持原目录。

两份现有路线图内容近乎相同，仅链接和少量注释不同。迁移时合并为一份权威版本，保留较完整内容并按新目录修正图片链接，不保留重复副本。

六周任务书统一采用以下文件名：

| 旧文件名 | 新文件名 |
|---|---|
| `AA_algo_a.md` | `aa-algorithm-a.md` |
| `AB_algo_b.md` | `ab-algorithm-b.md` |
| `DA_delivery_a.md` | `da-delivery-a.md` |
| `DB_delivery_b.md` | `db-delivery-b.md` |
| `EX_experiment.md` | `ex-experiment.md` |
| `IA_infra_a.md` | `ia-infrastructure-a.md` |
| `IB_infra_b.md` | `ib-infrastructure-b.md` |
| `TL_tech_lead.md` | `tl-technical-lead.md` |

### 4.4 output

| 归档目录 | 现有产物 |
|---|---|
| `output/archive/validation/` | `validate/`、`validate_quick/` |
| `output/archive/experiments/` | `w3_audit/`、`stress/`、`batch_smoke/` |
| `output/archive/checks/` | `seed_check/`、`cli_check/`、`cli_check2/`、pytest 临时目录、IB 断线检查日志 |

`output/csv/`、`output/logs/` 和 `output/variants/` 不移动。归档操作不得删除或覆盖同名产物。

## 五、路径兼容与代码调整

移动后的脚本从仓库根目录运行，例如：

```bash
python scripts/validation/validate_all.py
python scripts/data/generate_edge_mapping.py
bash scripts/quality/lint_check.sh
```

脚本中依赖文件位置的根目录推导统一调整。对于位于 `scripts/<category>/` 的 Python 文件，仓库根目录为：

```python
ROOT = Path(__file__).resolve().parents[2]
```

同时更新：

- 文档生成脚本的目标路径；
- Dockerfile 与 docker-compose 中的脚本引用；
- 根 README、模块 README 和 `docs/**/*.md` 中的本地链接与命令；
- 代码和配置中的有效文档路径；
- `.gitignore`，允许提交 `output/README.md` 与 `output/deliverables/README.md`。

历史设计文档中的可执行路径同步更新；纯历史叙述只修复链接，不改变结论。

## 六、README 规范

新增：

- `scripts/README.md`
- `tests/README.md`
- `output/README.md`
- `output/deliverables/README.md`

更新根 README、`docs/README.md`、`examples/README.md` 及各源码模块 README。模块 README 统一包含：

1. 模块职责
2. 文件索引
3. 公共接口或运行命令
4. 输入与输出
5. 依赖关系
6. 已知限制

模块 README 删除“当前完成情况/待完成情况”复选框。项目进度保留在 `docs/reports/` 和 `docs/team/tasks/`。

## 七、迁移流程

1. 建立完整的旧路径到新路径映射表。
2. 记录待移动文件数量和内容哈希。
3. 移动 `scripts/`，修正根路径推导与生成目标，完成脚本级验证。
4. 移动 `tests/`，立即执行完整测试并核对收集数量。
5. 移动并重命名 `docs/`，更新全部有效链接和命令。
6. 分类迁移历史 `output/` 产物，核对迁移前后数量。
7. 更新 `.gitignore`、目录 README、模块 README 和根 README。
8. 执行最终验证矩阵并检查 Git 差异。

各阶段独立验证，避免在失败后无法判断问题来源。

## 八、错误处理与保护措施

- 所有移动目标在操作前确认不存在，避免覆盖同名文件。
- 工作树中的已修改和未跟踪文件视为有效用户内容，移动时保留其完整内容。
- 不使用 Git 回滚、重置或 checkout 覆盖当前改动。
- Windows 大小写不敏感，重命名通过明确的中间路径或移动操作完成。
- 相对链接按 Markdown 文件的新位置重新计算，不依赖简单字符串替换。
- 归档历史输出前后核对文件数量；不删除任何无法明确判定为临时文件的产物。

## 九、验收矩阵

1. **文件完整性**：移动前后文件数量和哈希一致。
2. **Python 语法**：`python -m compileall algorithms api cloud core engine examples experiments ml scenes scripts visualization` 通过。
3. **测试**：`python -m pytest tests/ -q` 仍为 66 项通过，收集数量不减少。
4. **lint**：`bash scripts/quality/lint_check.sh` 输出 `clean`。
5. **脚本**：数据生成、快速验证、seed 检查从新路径运行成功。
6. **仿真**：固定配时 100 步冒烟退出码为 0。
7. **输出**：`csv/logs/variants` 原位保留，归档前后文件数量一致。
8. **Markdown**：全部本地相对链接指向存在的文件，不再存在有效旧路径引用。
9. **Git**：`git diff --check` 无错误，状态中不出现意外内容删除。

## 十、非目标

- 不重构业务代码或公共 Python API。
- 不修改算法行为、仿真逻辑或实验指标。
- 不重新生成原始数据、SUMO 配置或历史实验结果。
- 不删除历史输出、设计文档或审查记录；仅合并两份重复的项目路线图。
- 不为旧 `scripts/*.py` 路径保留兼容包装文件。
