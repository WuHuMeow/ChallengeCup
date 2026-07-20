# 雄安新区车路云协同管控算法与仿真平台

> XH-202613 · 路线 B：经典交通管控算法的场景适配与优化

## 项目状态

| 项目 | 状态 |
|------|------|
| 当前阶段 | 学习与知识库建设 |
| 技术路线 | 路线 B（算法调优型） |
| 版本 | v0.1 |
| 最近更新 | 2026-07-20 |

## 项目简介

面向雄安新区"城市大脑"车路云一体化场景，将经典交通信号控制算法应用于"窄路密网"路网，通过 SUMO 仿真平台进行参数调优与性能评估，并与传统固定配时方案进行对比验证。

## 快速导航

| 入口 | 说明 |
|------|------|
| [新人第一天指南](docs/guides/first-day.md) | 15 分钟完成环境搭建 |
| [仓库结构说明](PROJECT_STRUCTURE.md) | 每个目录的职责与权限 |
| [贡献指南](CONTRIBUTING.md) | Git 工作流与提交规范 |
| [知识中心](docs/README.md) | 所有文档、笔记、规范的入口 |
| [团队分工](docs/团队分工方案.md) | 4 组 × 2 人职责划分 |
| [当前任务](docs/tasks/current-tasks.md) | 本周各组的任务 |

## 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/<org>/xiong-an-traffic.git
cd xiong-an-traffic

# 2. 配置 Python 环境（二选一）
pip install -r requirements.txt        # pip 用户
conda env create -f environment.yml    # conda 用户

# 3. 验证 SUMO 安装
sumo --version
```

## 目录导航

| 目录 | 用途 | 负责人 |
|------|------|--------|
| `intersection_data/` | 主办方原始数据集（只读） | A 组 |
| `src/` | 源代码（算法、仿真、分析） | B 组为主 |
| `docs/` | 知识中心（文档、笔记、规范） | 全员 |
| `scripts/` | 运维/一次性脚本 | A 组 |
| `configs/` | 配置文件 | B 组 |
| `results/` | 实验输出（gitignore） | C 组 |
| `submission/` | 最终提交物 | D 组 |
| `references/` | 外部参考资料 | 全员 |
| `templates/` | 文档模板 | D 组 |
| `assets/` | 静态资源 | 全员 |
| `workspace/` | 临时工作区（gitignore） | 各组 |

## 团队

| 小组 | 定位 | Owner |
|------|------|-------|
| A 数据与仿真组 | 基础设施层 | TBD |
| B 算法研究组 | 核心智力层 | TBD |
| C 实验评估组 | 验证度量层 | TBD |
| D 项目管理与文档组 | 组织协调层 | TBD |

## 比赛信息

- 赛题编号：XH-202613
- 截止日期：2026-09-01（提交缓冲：09-15）
- 提交方式：发送至 497923691@qq.com

## License

[MIT](LICENSE)
