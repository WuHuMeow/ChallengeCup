# 主 README 对齐设计

> 日期：2026-07-24
>
> 范围：根 `README.md` 的内容基线、迁移路径修正、项目状态与团队分工状态

## 目标

根 README 以 GitHub `main` 分支的长版 README 为内容和版式基线，恢复项目概述、算法说明、数据说明、实验设计、团队分工、开发计划和提交材料等完整章节。目录整理分支当前的精简 README 不再作为主体，只保留其中已经由代码和验证证据确认的新事实。

## 内容策略

1. 保留 `main` README 的章节顺序、目录锚点、核心表格和项目叙事。
2. 修正目录迁移后失效的链接和命令：
   - `docs/pdf/` 改为 `docs/reference/competition/`。
   - `docs/tasks/` 改为 `docs/team/tasks/`，任务书文件名改为 kebab-case。
   - 路线图改为 `docs/team/project-roadmap.md`。
   - 架构图改为 `docs/architecture/images/`。
   - IA 报告、部署、环境和边映射文档改为 `docs/reports/`、`docs/operations/`、`docs/reference/` 下的规范路径。
   - 脚本命令改为 `scripts/data/`、`scripts/simulation/`、`scripts/validation/`、`scripts/quality/`。
3. SUMO 环境要求写为项目验证版本 1.27.1；不宣称其他版本已完成全量兼容验证。
4. 快速开始保留原有安装流程，同时增加 CA-MP 示例、pytest、lint 和实验 CLI 的当前命令。
5. 分支说明以 GitHub 当前实际状态为准：`main` 是稳定分支，功能改动通过独立分支和 PR 合入；删除旧的 stable/master 操作说明。
6. README 中保留明确的已知限制：CA-MP 的 MVI 相位桩、API 占位端点、ML 占位实现、精确指标校准和 Docker 未实机构建。

## 团队分工状态

团队表继续保留 TL、IA、IB、AA、AB、EX、DA、DB 八个角色，但状态按仓库证据更新，不把“存在文件”直接等同于“角色全部完成”。状态口径如下：

| 角色 | README 状态 | 已有证据 | 剩余工作 |
| --- | --- | --- | --- |
| TL | 部分完成 | 核心数据契约、算法接口、文档 taxonomy 和集成验证已落地 | 全项目最终集成与交付审查 |
| IA | 已完成（Docker 待实机验证） | 20 路口 SUMO 迁移、增强配置、边映射和批量验证报告 | Docker 跨机器实机构建回填 |
| IB | 已完成 | TraCI 桥接、seed、采样、断线韧性、EdgeChannel、step/events 日志、CLI 与 66 项回归验证 | 配合后续算法联调，不再列为基础设施缺口 |
| AA | 基础实现完成 | FixedTime 与 Actuated 控制器、测试和真实固定配时冒烟 | 全矩阵算法效果复核 |
| AB | 进行中 | CA-MP 管道和示例可运行 | 修复 MVI `set_phase` 相位值并完成真实算法效果实现 |
| EX | 部分完成 | 单次/批量 runner、seed/倍率、指标输出和 12 次审计证据 | 360 次完整实验、tripinfo 精确指标与统计分析 |
| DA | 待完成 | 仓库已有技术 Markdown 报告 | 最终 Word 报告、PPT 和提交排版 |
| DB | 部分完成 | Matplotlib 绘图接口已存在 | PyQt 看板、视频录制和成片 |

README 的“当前状态”“团队分工”“提交材料”三处状态必须保持一致。IB 写为已完成时，同时保留 AB、EX、Docker 等非 IB 风险，避免将整个项目误写为已完成。

## 验收

- 根 README 的主要章节和叙事来自 `github/main:README.md`，而不是当前精简版。
- 原长版的目录、项目概述、核心算法、数据、实验、团队、计划和提交章节均存在。
- 所有本地 Markdown 链接可解析，活跃内容不引用迁移前路径。
- 团队八个角色均有当前完成状态、证据和剩余项。
- `python -m pytest tests/ -q`、`bash scripts/quality/lint_check.sh` 和 Markdown 链接检查通过。
- 变更提交并推送到 `codex/repository-structure-optimization`，不直接修改远端 `main`。
