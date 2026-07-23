# docs/

## 模块职责

存放项目全部文档，包括赛题 PDF、设计文档、接口文档、团队任务书、实验报告等提交材料。

## 当前完成情况

- [x] `pdf/XH-202613_...pdf`：发榜单位提供的原始赛题 PDF。
- [x] `tasks/`：团队任务书（roadmap + w1~w6 周任务书，8 人）；IA 各周任务书已标注完成状态（2026-07-23）。
- [x] `guides/`：协作与文档书写指南（Git 工作流、Markdown、引用方法）。
- [x] `superpowers/specs/`：设计文档（含 2026-07-23 CA-MP 完整实现设计）。
- [x] `interface.md`：接口文档（数据契约、算法接口、使用示例）。
- [x] `总路线.md`：项目总路线图（六周里程碑）。
- [x] `migration_log.md`：SUMO 版本迁移记录（IA，20/20 兼容）。
- [x] `batch_validate_report.md`：3600 步全量验证报告（IA，20/20 PASS）。
- [x] `edge_mapping.md`：20 路口边 ID → 方向映射表（IA）。
- [x] `sumo_env_setup.md`：SUMO 环境安装指南（IA）。
- [x] `deployment.md`：部署运行说明文档（IA，赛题硬性提交材料）。
- [x] `notes/docker_sumo_research.md`：Docker 运行 SUMO 调研笔记（IA）。
- [ ] `数据流图.png`：车-路-云数据流图（待创建）。

## 待完成情况

- [ ] IB 编写 Postman Collection。
- [ ] IB 绘制 `数据流图.png`。
- [ ] DA + EX 编写实验评估报告。
- [ ] DA 编写系统设计与算法报告。

## 关键文件

| 文件 | 说明 |
|------|------|
| `pdf/` | 赛题 PDF |
| `interface.md` | 接口文档（数据契约） |
| `tasks/` | 团队任务书（roadmap + w1~w6） |
| `guides/` | 协作与文档书写指南 |
| `superpowers/specs/` | 设计文档 |
| `总路线.md` | 项目总路线图 |
| `migration_log.md` / `batch_validate_report.md` | IA 迁移与全量验证报告 |
| `edge_mapping.md` | 边-方向映射表（算法组使用） |
| `sumo_env_setup.md` / `deployment.md` | 环境安装与部署运行说明 |

## 负责人

- TL：架构设计文档、接口定义
- IB：部署文档、接口文档
- DA：报告撰写、PPT
- EX：实验报告数据
