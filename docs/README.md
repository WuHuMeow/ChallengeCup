# 项目文档索引

`docs/` 是仓库文档入口，当前运行命令以根目录 `README.md`、本页和各模块 README 为准。

原 `docs/architecture/`、`docs/operations/`、`docs/reference/`、`docs/reports/` 和 `docs/team/` 目录暂作为历史兼容副本保留；新文档入口统一使用本页列出的平铺路径。

## 规范入口

| 文档 | 内容 |
| --- | --- |
| [总路线.md](总路线.md) | 项目目标、六周里程碑、实验设计和交付物 |
| [interface.md](interface.md) | 数据契约、算法接口、引擎接口、API 和实验 CLI |
| [deployment.md](deployment.md) | 本地、Docker 和完整实验运行方式 |
| [sumo_env_setup.md](sumo_env_setup.md) | SUMO 安装、环境变量和版本检查 |
| [edge_mapping.md](edge_mapping.md) | 20 个路口边 ID、方向和进出口属性 |
| [migration_log.md](migration_log.md) | SUMO 版本迁移记录 |
| [batch_validate_report.md](batch_validate_report.md) | 增强配置批量验证结果 |
| [ia-ib-final-verification.md](ia-ib-final-verification.md) | IA/IB 最终验收命令、退出码和证据 |
| [guides/](guides/) | Git、Markdown、数据导入、实验和测试指南 |
| [tasks/](tasks/) | Gitee 风格的路线图和每周任务书 |
| [superpowers/specs/](superpowers/specs/) | 架构、接口和算法设计文档及图示 |

## 文档目录

- `pdf/`：赛题原始 PDF。
- `tasks/`：路线图与 W1-W6 任务书。
- `guides/`：协作和运行指南。
- `superpowers/`：设计规格、实施计划和架构图。
- `notes/`：调研与技术选型记录。
- `report/`：报告交付目录，位于仓库根目录。

## 文档命令

以下命令从仓库根目录执行：

```powershell
python scripts/validate_all.py --output-root output/verification/original
python scripts/batch_validate.py --output-root output/verification/enhanced --no-report
python scripts/generate_edge_mapping.py
```

`batch_validate.py` 更新 `docs/batch_validate_report.md`，`generate_edge_mapping.py` 更新 `docs/edge_mapping.md`。

## 图示

- [系统架构图](superpowers/specs/images/architecture.svg)
- [仿真循环图](superpowers/specs/images/simulation-loop.svg)
- [模块依赖图](superpowers/specs/images/dependencies.svg)
- [开发时间线](superpowers/specs/images/timeline.svg)

## 约束

- 任务书描述计划和验收口径，不替代源码当前行为。
- 报告中的日期、性能和验证结论只适用于报告注明的环境与提交状态。
- SUMO 相关验证需要 `sumo` 位于 `PATH`。
