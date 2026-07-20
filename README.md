# XH-202613 | 容量感知最大压力信号控制（CA-MP）

> 面向雄安新区"城市大脑"的车路云一体化协同管控算法与仿真平台研究
> 赛道 B（算法调优型）

[![编号 XH-202613](https://img.shields.io/badge/%E7%BC%96%E5%8F%B7-XH--202613-orange)](./docs/pdf/)
[![赛道 B](https://img.shields.io/badge/%E8%B5%9B%E9%81%93-B%EF%BC%88%E7%AE%97%E6%B3%95%E8%B0%83%E4%BC%98%E5%9E%8B%EF%BC%89-green)](./docs/pdf/)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python)](https://www.python.org)
[![SUMO](https://img.shields.io/badge/SUMO-1.18+-brightgreen)](https://www.eclipse.org/sumo/)

---

## 项目简介

本项目针对雄安新区"窄路密网"交通场景（路口间距短、进口道容量低、排队回溢快），提出 **CA-MP（Capacity-Aware MaxPressure）** 信号控制算法。在经典 MaxPressure 算法基础上，引入三项改进：

1. **容量归一化压力**：用 `queue/capacity` 替代绝对排队数，短车道自动获得高优先级
2. **溢出门控**：进口道占用率 > 90% 时强制放行，防止窄路堵死
3. **云端动态绿灯时长**：CloudCoordinator 根据全局压力周期性下发参数

结合 EWMA 轻量流量预测，实现"云-边-端"三层协同信号控制。

---

## 快速开始

### 环境要求

- Python 3.10+
- SUMO 1.18+（[下载地址](https://www.eclipse.org/sumo/)）
- 设置环境变量 `SUMO_HOME` 指向 SUMO 安装目录

### 安装依赖

```bash
git clone https://github.com/WuHuMeow/ChallengeCup.git
cd ChallengeCup
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS
pip install -r requirements.txt
```

### 运行仿真

路口数据已随仓库提交，位于 `data/intersection_data/`，无需额外配置路径。

```bash
# 运行路口 1 的固定配时基线仿真
python examples/run_fixed_time.py 1

# 启动 FastAPI 服务（可选）
uvicorn api.server:app --reload
```

---

## 项目结构

```text
ChallengeCup/
├── core/                       # 全项目共享核心
│   ├── types.py                # JointState / ControlAction / SceneMeta 等数据契约
│   └── config.py               # YAML 配置加载
├── engine/                     # 仿真引擎（SUMO + TraCI）
│   ├── runner.py               # 单次仿真实验运行器
│   ├── traci_bridge.py         # TraCI 批量读写桥接
│   └── collector.py            # 每步状态与指标 CSV 采集
├── scenes/                     # 场景管理
│   ├── registry.py             # 20 路口元数据索引（兼容高精地图/高清地图命名差异）
│   ├── variant.py              # 流量变体生成
│   └── timing_loader.py        # 从 Excel 读取信号配时方案
├── algorithms/                 # 算法库
│   ├── base.py                 # BaseControlAlgorithm 标准接口（ABC）
│   ├── fixed_time.py           # 固定配时基线
│   ├── rule_adaptive.py        # 规则自适应（感应控制）
│   └── ml_enhanced.py          # CA-MP + EWMA 增强（核心创新）
├── cloud/                      # 云端策略层
│   └── cloud_policy.py         # CloudCoordinator 全局参数下发
├── ml/                         # ML 模型模块
│   ├── train.py                # EWMA / XGBoost 训练
│   ├── features.py             # 特征工程
│   └── evaluate.py             # 模型评估
├── api/                        # REST API
│   └── server.py               # FastAPI 应用
├── experiments/                # 实验分析框架
│   ├── runner.py               # 多场景多算法交叉跑批
│   └── metrics.py              # 指标采集
├── visualization/              # 可视化
│   └── plots.py                # Matplotlib 图表
├── config/
│   └── default.yaml            # 全局配置
├── data/                       # 数据集
│   ├── intersection_data/      # 20 个路口原始数据
│   ├── intersection_data/metadata/  # 路口元数据（CSV + YAML）
│   └── intersection_data.zip   # 路口数据压缩包
├── examples/
│   └── run_fixed_time.py       # 最小可运行示例
├── docs/                       # 文档
│   ├── pdf/                    # 赛题 PDF
│   ├── tasks/                  # 团队任务书（roadmap + w1~w6）
│   ├── guides/                 # 协作指南
│   └── superpowers/specs/      # 设计文档
├── requirements.txt
├── LICENSE
├── .gitignore
└── README.md
```

---

## 核心算法

### 云-边-端架构

```
Cloud (CloudCoordinator)
  │  CloudCommand: 周期性下发 min_green/max_green/base_green
  ▼
Edge (EdgeNode / RSU)
  │  调用 CA-MP 算法，输出 SignalAction
  ▼
Vehicle (V2XMessage)
     上报位置、速度、车道 → 边缘节点
```

### CA-MP 决策逻辑

```python
# 1. 溢出门控：占用率 > 90% → 强制放行
# 2. 容量归一化：pressure = queue / capacity
# 3. 选最大压力相位
# 4. 动态绿灯时长：duration = base_green * (phase_pressure / avg_pressure)
```

---

## 实验设计

| 维度 | 方案 |
|------|------|
| 路口 | 20 个（主办方提供） |
| 算法 | CA-MP / FixedTime / Actuated（3 种） |
| 流量 | 原始流量 + 1.5 倍压力（2 档） |
| 重复 | 每组 3 次（随机种子 42/123/456） |
| 总计 | 20 × 3 × 2 × 3 = 360 次仿真 |
| 指标 | 平均行程时间、排队长度、吞吐量、油耗、延误、停车次数 |

---

## 团队分工

| 代号 | 角色 | 人数 | 职责概述 |
|------|------|------|----------|
| TL | Tech Lead | 1 | 架构设计、接口定义、代码合入、集成协调 |
| IA | 仿真基础设施 A | 1 | SUMO 版本统一、20 路口迁移验证 |
| IB | 仿真基础设施 B | 1 | SumoSimulator 封装、TraCI 接口、云-边-端消息流 |
| AA | 算法 A | 1 | FixedTimeController + ActuatedController（基线） |
| AB | 算法 B | 1 | CAMaxPressureController（核心创新）+ EWMA 预测 |
| EX | 实验组 | 1 | 实验矩阵设计、批量运行、指标采集、统计分析 |
| DA | 交付 A | 1 | 报告撰写、PPT 制作、文档排版 |
| DB | 交付 B | 1 | 可视化（Matplotlib 图表 + PyQt 看板）、视频录制剪辑 |

详细任务书见 [`docs/tasks/`](docs/tasks/roadmap.md)。

---

## 六周里程碑

| 周 | 日期 | 里程碑 | 验收标准 |
|----|------|--------|----------|
| W1 | 7/20 - 7/26 | 框架搭建 | 单路口（路口1）固定配时 + CA-MP 均可跑通 3600 步；接口冻结 |
| W2 | 7/27 - 8/2 | 算法联调 | 云-边-端消息流贯通；CA-MP 在路口 1 出对比数据；感应控制基线完成 |
| W3 | 8/3 - 8/9 | 全量实验 | 20 路口 × 3 算法 × 原始流量第一轮跑完；Matplotlib 图表产出 |
| W4 | 8/10 - 8/16 | 压力测试 + 调优 | 1.5 倍流量实验完成；EWMA 预测接入；Docker 打包 |
| W5 | 8/17 - 8/23 | 交付物制作 | 报告初稿、PPT 初稿、视频脚本 + 录制完成 |
| W6 | 8/24 - 8/31 | 打磨提交 | 全员 review、修 bug、视频剪辑定稿、最终提交（8/31 前） |

---

## 数据说明

`data/intersection_data/` 包含 20 个雄安路口的原始数据，编号 1 至 20。每个路口：

```text
intersection_data/{id}/
├── sumo工程/
│   ├── algorithm.py              # TraCI 启动模板
│   ├── demo_{id}.net.xml         # SUMO 路网文件
│   ├── demo_{id}.rou.xml         # 车辆行驶路径
│   ├── demo_{id}.flow.xml        # 交通流量定义
│   ├── demo_{id}.turn.xml        # 转向比例定义
│   └── demo_{id}.sumocfg         # SUMO 仿真配置
├── 路口数据/
│   └── demo_{id}流量和交叉口配时方案.xlsx
└── 高精地图/
    └── demo_{id}.png
```

元数据汇总见 `data/intersection_data/metadata/`。

---

## 协作指南

| 指南 | 说明 |
|------|------|
| [Git 工作流](./docs/guides/git-workflow.md) | 克隆、提交、推送、解决冲突 |
| [Markdown 书写方法](./docs/guides/markdown-guide.md) | 常用 Markdown 语法 |
| [引用方法](./docs/guides/citation-guide.md) | 规范引用文献、图片、代码 |

---

## 提交材料

| # | 交付物 | 格式 | 负责人 |
|---|--------|------|--------|
| 1 | PPT 汇报 | .pptx | DA |
| 2 | 可运行仿真系统 + 源代码 | 代码仓库 | TL 集成 |
| 3 | 部署运行说明文档 | docs/ | IB |
| 4 | 实验评估报告 | Word | DA + EX |
| 5 | 演示视频（5-8 分钟） | .mp4 | DB |
| 6 | Dockerfile + 部署文档 | Dockerfile + docs/ | IB |

---

## 许可与致谢

[MIT](LICENSE)

本项目为挑战杯 2026 参赛作品（编号 XH-202613），技术方案参考竞赛官方 PDF 要求与雄安新区"城市大脑"车路云一体化场景需求。
