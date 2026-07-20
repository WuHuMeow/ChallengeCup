# 仓库工程说明书

> 本文面向团队成员，说明仓库每个目录的职责、权限和使用规则。

## 目录职责与权限

| 目录 | 职责 | 权限 | 负责人 |
|------|------|------|--------|
| `intersection_data/1~20/` | 主办方原始数据 | 只读 | A 组 |
| `intersection_data/metadata/` | 路口元数据（派生） | 可写 | A 组 |
| `src/algorithms/` | 信号控制算法实现 | 可写 | B 组 |
| `src/simulation/` | SUMO 仿真驱动 | 可写 | A/B 组 |
| `src/analysis/` | 数据分析与可视化 | 可写 | C 组 |
| `src/interfaces/` | 算法/TraCI 接口封装 | 可写 | B 组 |
| `src/common/` | 公共工具 | 可写 | 全员 |
| `scripts/` | 一次性/运维脚本 | 可写 | A 组 |
| `configs/` | 仿真/实验参数配置 | 可写 | B/C 组 |
| `docs/guides/` | 新人指南、操作指南 | 可写 | D 组为主 |
| `docs/tasks/` | 任务管理 | 可写 | D 组 |
| `docs/research/` | 算法调研笔记 | 可写 | B 组 |
| `docs/intersections/` | 20 路口档案 | 可写 | A 组 |
| `docs/experiments/` | 实验设计与指标 | 可写 | C 组 |
| `docs/meetings/` | 周会记录 | 可写 | D 组 |
| `docs/decisions/` | ADR 决策记录 | 可写 | 全员 |
| `docs/standards/` | 规范文档 | 可写 | D 组 |
| `docs/faq/` | 常见问题 | 可写 | 全员 |
| `docs/glossary/` | 术语表 | 可写 | 全员 |
| `results/` | 实验输出（gitignore） | 自由 | 全员 |
| `submission/` | 最终提交物 | 可写 | D 组为主 |
| `references/` | 外部参考资料 | 可写 | 全员 |
| `templates/` | 文档模板 | 可写 | D 组 |
| `assets/` | 静态资源 | 可写 | 全员 |
| `workspace/` | 临时工作区（gitignore） | 自由 | 各组 |

## 新增文件规范

1. 新增一级目录必须同时创建 `README.md`
2. 新增二级目录如果承担长期维护职责，也应创建 `README.md`
3. 文件命名规则见 [CONTRIBUTING.md](CONTRIBUTING.md#文件命名)
4. 不确定放哪里时，先放 `workspace/` 自己的组目录，周会时讨论归档位置

## 只读规则

`intersection_data/1~20/` 中的文件原则上不修改。如果确实发现数据错误：
1. 在 `docs/faq/` 中记录问题
2. 周会提出讨论
3. 团队确认后由 A 组 Owner 统一修正
4. commit message 注明 `fix(A): 修正路口N数据错误（经团队确认）`
