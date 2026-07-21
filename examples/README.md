# examples/

## 模块职责

存放最小可运行示例，帮助 teammates 快速理解如何运行单次仿真和批量实验。

## 当前完成情况

- [x] `run_demo.py`：全链路演示（默认 Mock 模式，加 `--sumo` 使用真实仿真），验证 config → scene → engine → algorithm → cloud → collector → metrics 完整调用链。
- [x] `run_fixed_time.py`：运行单个路口固定配时基线仿真的示例脚本（需 SUMO）。

## 待完成情况

- [ ] `run_batch.py`：多场景多算法批量跑批示例。

## 需求分析

| 需求 | 说明 |
|------|------|
| 快速上手 | 新队员通过示例脚本 1 分钟跑通第一个仿真 |
| 算法对比 | 提供同一场景下三种算法运行的示例 |
| 批量实验 | 提供 360 次全量跑批的示例 |

## 关键文件

| 文件 | 说明 |
|------|------|
| `run_demo.py` | 全链路演示（Mock / SUMO） |
| `run_fixed_time.py` | 固定配时基线示例（需 SUMO） |

## 使用方式

```bash
# 全链路演示（无需 SUMO）
python examples/run_demo.py 1 ca_maxpressure

# 使用真实 SUMO 仿真
python examples/run_demo.py 1 ca_maxpressure --sumo

# 固定配时基线（需 SUMO）
python examples/run_fixed_time.py 1
```

## 负责人

- IB（仿真基础设施 B）：维护仿真相关示例
- AA/AB（算法）：维护算法示例
- EX（实验组）：维护批量示例
