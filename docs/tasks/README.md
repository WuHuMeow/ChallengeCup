# 团队任务书索引

`w1/` 至 `w6/` 保存 8 个角色的周任务书，记录阶段性目标、设计草案、验收口径和历史协作安排。

## 目录

| 周次 | 目录 |
| --- | --- |
| W1 | [w1/](w1/) |
| W2 | [w2/](w2/) |
| W3 | [w3/](w3/) |
| W4 | [w4/](w4/) |
| W5 | [w5/](w5/) |
| W6 | [w6/](w6/) |

每周目录包含算法、交付、实验、基础设施和技术负责人等角色的任务书。任务书中的 `[ ]` 项、未来脚本名和示例命令描述当时计划或验收口径，不代表这些功能或文件当前存在，也不应直接复制执行。

## 当前验证状态

本目录的周次、日期和复选框保留历史计划状态，不表示当前缺陷或完成度。当前仓库是内部研发仓库：功能一、功能二作为共同基础完成，项目选择赛道 B，聚焦 CA-MP 的场景适配、参数调优和性能评估。

IA/IB 当前状态以 [`docs/ia-ib-final-verification.md`](../ia-ib-final-verification.md) 为准：13 项检查通过，Docker live 与第二机器复现保持 `not_run`。大体积仿真结果及压缩包已删除；清理记录和重新生成入口见 [`docs/ia-ib-simulation-artifact-cleanup.md`](../ia-ib-simulation-artifact-cleanup.md)。

## 当前入口

- 当前脚本分类、命令、输入输出和限制：[`scripts/README.md`](../../scripts/README.md)。
- 当前仓库快速开始和验证命令：[`README.md`](../../README.md)。
- 当前测试入口：

  ```powershell
  python -m pytest tests/ -q
  ```

- 当前文档分类和规范资料：[`docs/README.md`](../README.md)。

## 依赖与限制

任务书是 Markdown 历史/计划资料，不参与 Python 运行时，也不提供可执行脚本依赖。涉及旧目录、旧测试名或尚未落地的 dashboard、audit、scale_flow 等脚本时，应以当前脚本索引和源码为准。
