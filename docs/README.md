# 项目文档索引

`docs/` 是当前文档地图。当前命令以根目录 [`README.md`](../README.md) 和活跃操作指南为准；`docs/superpowers/` 与 `docs/tasks/` 分别保留历史设计决策和周任务安排，不替代当前运行说明。

## 当前入口

- [项目说明、快速开始和当前验证命令](../README.md)
- [数据契约、算法接口、引擎接口和 API](interface.md)
- [部署与复现说明](deployment.md)
- [SUMO 环境安装与版本检查](sumo_env_setup.md)
- [操作指南](guides/)

## PDF 与验收依据

- [原始赛题 PDF](pdf/XH-202613_面向雄安新区“城市大脑”的车路云.pdf)
- [IA/IB 最终验收](ia-ib-final-verification.md)：13 项检查通过，Docker live 与第二机器复现保持 `not_run`。
- [仿真产物清理记录](ia-ib-simulation-artifact-cleanup.md)：大体积仿真结果及压缩包已删除，按复现指南重新生成。

## 操作与参考资料

- [20 个路口边 ID 与方向映射](edge_mapping.md)
- [SUMO 版本迁移记录](migration_log.md)
- [增强配置批量验证报告](batch_validate_report.md)
- [调研与技术选型记录](notes/)

## 历史设计和周任务

- [项目总路线](总路线.md)：保留六周计划和角色安排；当前 IA/IB 状态以验收记录为准。
- [周任务书与路线图](tasks/)
- [历史设计与实施记录](superpowers/)
