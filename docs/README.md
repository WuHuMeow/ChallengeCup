# 项目文档索引

`docs/` 面向评委与使用者组织。当前命令以根目录 [`README.md`](../README.md)、
[发布文档](release/README.md) 和本页入口为准。

## 当前入口

- [评委快速开始与当前证据状态](../README.md)
- [发布文档总览](release/README.md)
- [实验协议（540-run 矩阵与统计判定）](release/experiment-protocol.md)
- [证据合同（产物字段与单位）](release/evidence-contract.md)
- [算法扩展指南](release/algorithm-extension.md)
- [数据契约、模块接口与架构](interface.md)
- [部署与复现说明](deployment.md)
- [SUMO 环境安装与版本检查](sumo_env_setup.md)
- [操作指南](guides/)

最小验证入口（输出目录由命令在运行时创建）：

```powershell
python scripts/run_pdf_matrix.py --profile smoke --output-root output/runs/matrix-smoke
python scripts/run_pdf_matrix.py --profile quick --output-root output/runs/matrix-quick
python scripts/validate_all.py --output-root output/runs/validate-original
python scripts/batch_validate.py --output-root output/runs/validate-enhanced --no-report
```

## 参考资料

- [原始赛题 PDF](pdf/)（含 XH-202613 题目与评分说明）
- [20 个路口边 ID 与方向映射](edge_mapping.md)
- [SUMO 版本迁移记录](migration_log.md)
- [增强配置批量验证报告](batch_validate_report.md)
- [调研与技术选型记录](notes/)

## 历史设计记录

- 内部设计与实施记录（`docs/superpowers/`，仅仓库内保留，不随发布副本分发）
  按任务归档设计、计划与台账，仅作历史依据，不替代当前运行说明。
