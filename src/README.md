# 源代码

> 项目统一入口：`python src/main.py`

## 模块划分

| 目录 | 职责 | 负责人 |
|------|------|--------|
| `algorithms/` | 信号控制算法实现 | B 组 |
| `simulation/` | SUMO 仿真驱动、批量运行 | A/B 组 |
| `analysis/` | 数据分析与可视化 | C 组 |
| `interfaces/` | 算法接口、TraCI 封装 | B 组 |
| `common/` | 公共工具、配置读取、日志 | 全员 |

## 运行方式（开发阶段启用）

```bash
python src/main.py --mode simulation --intersection 1 --algorithm webster
```

## 当前状态

尚未进入开发阶段。目录结构已就绪，待算法方案确定后开始编码。
