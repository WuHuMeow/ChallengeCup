# XH-202613 | 容量感知最大压力信号控制（CA-MP）

> 面向雄安新区"城市大脑"的车路云一体化协同管控算法与仿真平台研究
> 赛道 B（算法调优型）

## 项目简介

本项目针对雄安新区"窄路密网"交通场景（路口间距短、进口道容量低、排队回溢快），提出 **CA-MP（Capacity-Aware MaxPressure）** 信号控制算法。在经典 MaxPressure 算法基础上，引入三项改进：

1. **容量归一化压力**：用 `queue/capacity` 替代绝对排队数，短车道自动获得高优先级
2. **溢出门控**：进口道占用率 > 90% 时强制放行，防止窄路堵死
3. **云端动态绿灯时长**：CloudCoordinator 根据全局压力周期性下发参数

结合 EWMA 轻量流量预测，实现"云-边-端"三层协同信号控制。

## 快速开始

### 环境要求

- Python 3.10+
- SUMO 1.26.0+（[下载地址](https://sumo.dlr.de/docs/Downloads.html)）
- 设置环境变量 `SUMO_HOME` 指向 SUMO 安装目录

### 安装依赖

```bash
pip install -r requirements.txt
```

### 解压数据

```bash
# 将 data/intersection_data.zip 解压到项目根目录
python -c "import zipfile; zipfile.ZipFile('data/intersection_data.zip').extractall('.')"
```

### 运行仿真

```bash
# 路口 16，CA-MP 算法，3600 步
python src/platform/main.py --intersection 16 --algo ca_maxpressure --steps 3600

# 路口 1，固定配时基线
python src/platform/main.py --intersection 1 --algo fixed_time --steps 3600

# 带 GUI 可视化
python src/platform/main.py --intersection 16 --algo ca_maxpressure --steps 3600 --gui
```

### Docker 运行

```bash
docker build -t ca-mp .
docker run --rm ca-mp --intersection 16 --algo ca_maxpressure --steps 3600
```

## 项目结构

```
├── src/
│   ├── common/
│   │   └── messages.py          # V2XMessage, EdgeStatus, CloudCommand, SignalAction
│   ├── platform/
│   │   ├── simulator.py         # SumoSimulator (TraCI 封装)
│   │   ├── edge_node.py         # EdgeNode (RSU 边缘节点)
│   │   ├── cloud.py             # CloudCoordinator (云端协调)
│   │   └── main.py              # 主循环入口
│   ├── algorithm/
│   │   ├── base.py              # BaseController 抽象基类
│   │   ├── fixed_time.py        # 固定配时（基线）
│   │   ├── actuated.py          # 感应控制（基线）
│   │   ├── ca_max_pressure.py   # CA-MP（核心创新）
│   │   └── ewma_predictor.py    # EWMA 流量预测
│   └── visualization/
│       ├── plots.py             # Matplotlib 图表生成
│       └── dashboard.py         # PyQt 实时看板
├── experiments/
│   ├── config.yaml              # 实验矩阵配置
│   ├── runner.py                # 批量运行脚本
│   └── collector.py             # 指标采集
├── data/
│   └── intersection_data.zip    # 20 路口 SUMO 数据（解压到根目录使用）
├── docs/
│   ├── deployment.md            # 部署文档
│   ├── interface.md             # 接口文档
│   └── tasks/                   # 团队任务书
├── report/                      # 实验评估报告
├── slides/                      # 答辩 PPT
├── demo/                        # 演示视频素材
├── Dockerfile
├── requirements.txt
├── XH-202613.pdf                # 赛题文档
└── LICENSE
```

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

## 实验设计

- **路口**：20 个（主办方提供）
- **算法**：CA-MP / FixedTime / Actuated
- **流量**：原始 + 1.5 倍压力
- **重复**：每组 3 次（随机种子 42/123/456）
- **指标**：平均行程时间、排队长度、吞吐量、油耗、延误、停车次数

## 团队

| 角色 | 职责 |
|------|------|
| Tech Lead | 架构设计、接口定义、集成协调 |
| 仿真基础设施 ×2 | SUMO 环境、TraCI 封装、Docker 部署 |
| 算法 ×2 | CA-MP 实现、基线算法、EWMA 预测 |
| 实验 | 实验矩阵、批量运行、统计分析 |
| 交付 ×2 | 报告、PPT、可视化、视频 |

## 赛题文档

见 `XH-202613.pdf`（主办方原始赛题说明）。

## License

[MIT](LICENSE)
