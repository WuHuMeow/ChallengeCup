# 项目文档索引

`docs/` 是仓库文档的规范入口。当前运行命令应以本页、根目录 `README.md` 和各模块 README 为准；`superpowers/` 下的设计与实施计划属于历史过程记录，其中的旧目录名和旧命令不构成当前操作说明。

## 文档分类

| 目录 | 职责 | 主要输入 | 主要输出 |
| --- | --- | --- | --- |
| `architecture/` | 数据契约、模块接口和调用关系 | 当前源码接口 | 接口说明 |
| `operations/` | 环境安装、部署与运行 | SUMO/Python/Docker 环境 | 可执行运维步骤 |
| `reference/` | 赛题原文和生成的技术映射 | 官方资料、路网 XML | PDF、边方向映射 |
| `reports/` | 验证、迁移和审计结果 | 脚本输出、测试记录 | 可复核报告 |
| `notes/` | 调研与技术选型背景 | 外部资料、实验记录 | 非规范性笔记 |
| `guides/` | Git、Markdown 和引用规范 | 团队协作约定 | 操作指南 |
| `team/` | 项目路线图和每周任务书 | 项目计划 | 任务与验收口径 |
| `superpowers/` | 历史设计、实施计划和设计图 | 阶段性需求 | 决策与迁移记录 |

## 规范入口

| 文档 | 内容 |
| --- | --- |
| [architecture/README.md](architecture/README.md) | 当前架构文档与图示索引 |
| [architecture/interface.md](architecture/interface.md) | 核心数据类、算法接口、引擎接口、API 和实验 CLI |
| [operations/sumo-environment-setup.md](operations/sumo-environment-setup.md) | SUMO 安装、环境变量和版本检查 |
| [operations/deployment.md](operations/deployment.md) | 本地、Docker 和完整实验运行方式 |
| [reference/edge-mapping.md](reference/edge-mapping.md) | 20 个路口边 ID、方向和进出口属性 |
| [reports/sumo-migration-log.md](reports/sumo-migration-log.md) | SUMO 兼容性迁移记录 |
| [reports/batch-validation-report.md](reports/batch-validation-report.md) | 增强配置批量验证结果 |
| [team/project-roadmap.md](team/project-roadmap.md) | 六周项目路线图 |
| [guides/README.md](guides/README.md) | 协作指南索引 |

## 团队任务

任务书描述计划、交付物和验证口径，不应作为源码当前状态清单使用。

任务书的历史/计划性质和当前命令入口见 [team/tasks/README.md](team/tasks/README.md)。

| 周次 | 目录 |
| --- | --- |
| W1 | [team/tasks/w1/](team/tasks/w1/) |
| W2 | [team/tasks/w2/](team/tasks/w2/) |
| W3 | [team/tasks/w3/](team/tasks/w3/) |
| W4 | [team/tasks/w4/](team/tasks/w4/) |
| W5 | [team/tasks/w5/](team/tasks/w5/) |
| W6 | [team/tasks/w6/](team/tasks/w6/) |

## 参考资料与图示

- [reference/competition/](reference/competition/) 保存赛题原始 PDF。
- [notes/docker-sumo-research.md](notes/docker-sumo-research.md) 记录 Docker 基础镜像和 SUMO 版本选型背景。
- [architecture/images/architecture.svg](architecture/images/architecture.svg) 是系统架构图。
- [architecture/images/simulation-loop.svg](architecture/images/simulation-loop.svg) 是仿真循环图。
- [architecture/images/dependencies.svg](architecture/images/dependencies.svg) 是模块依赖图。

## 文档命令

以下命令从仓库根目录执行：

```powershell
python scripts/validation/validate_all.py
python scripts/validation/batch_validate.py
python scripts/data/generate_edge_mapping.py
```

`batch_validate.py` 会更新 `reports/batch-validation-report.md`，`generate_edge_mapping.py` 会更新 `reference/edge-mapping.md`。生成文件的来源和覆盖行为见 [scripts/README.md](../scripts/README.md)。

## 依赖

- Markdown 文档可直接阅读；运行示例命令需要项目 Python 环境。
- SUMO 相关验证需要 `sumo` 位于 `PATH`。
- PDF 和 SVG 只作为参考资料，不参与 Python 运行时。

## 已知限制

- `superpowers/` 中的设计和实施计划保留阶段性范围、旧路径迁移表及历史代码片段；执行命令前必须回到当前 README 或脚本索引确认路径。
- 团队任务书可能包含尚未实现的目标，不等同于功能承诺。
- 报告中的日期、性能和验证结论只适用于报告注明的环境与提交状态。
