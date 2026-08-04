# 证据目录

本目录存放各阶段验收的不可变证据文件。运行产物默认被 `.gitignore` 忽略，只有经审阅的小型 Markdown/JSON 清单允许窄范围追踪。

## 目录结构

| 目录 | 用途 | 冻结条件 |
|---|---|---|
| `baseline/` | 质量基线证据（测试、编译、SUMO 实跑） | 198 passed，质量门禁全绿 |
| `docker/` | Docker live 构建、运行、导出、导入证据 | Docker 全流程真实执行通过 |
| `second-machine/` | 第二台电脑复现证据 | 源码路线和 Docker 路线均通过 |
| `matrix-preflight/` | 预实验与参数冻结 | 54 组全部 completed |
| `matrix-final/` | 正式 360 组矩阵 | 360 组全部 completed |
| `statistics/` | 配对统计分析 | 12 个检验完成，来源可追溯 |
| `figures/` | 正式图表 | manifest 通过审计 |
| `final-acceptance/` | 最终验收 | 所有检查 pass |

## 证据文件规范

每个冻结目录必须包含：
- 执行命令及完整参数
- 环境版本（Python/SUMO/Git commit）
- 退出码
- ISO 8601 时间戳
- 文件 SHA-256 校验值

## 清理规则

- 运行产物默认不提交 Git
- 已冻结证据在对应阶段未解冻时不得删除
- 不得把已删除的历史产物描述为当前存在

## 参考

- [提交收敛进度](../../docs/tasks/submission-progress.md)
- [提交收敛计划](../../docs/superpowers/plans/2026-07-30-submission-completion.md)
- [提交收敛设计](../../docs/superpowers/specs/2026-07-30-submission-completion-design.md)
