# 如何配置云端协调器

## 目的

调整 CloudCoordinator（EWMA 流量预测 + 动态参数下发）的行为参数。

## 前置条件

- 了解 CA-MP 算法的云端协同机制（参见 `docs/architecture/interface.md`）
- 已安装项目依赖：`pip install -e .`

## 操作步骤

1. 打开 `config/default.yaml`，定位 `algorithms.ca_maxpressure` 节：

```yaml
  ca_maxpressure:
    ewma_alpha: 0.3            # EWMA 平滑系数
    prediction_horizon: 300    # 预测时域（秒）
    cloud_update_interval: 600 # 下发间隔（仿真步）
```

2. 调整参数：
   - `ewma_alpha`：0~1，越大对新流量越敏感（推荐 0.2~0.5）
   - `prediction_horizon`：预测未来多少秒的流量
   - `cloud_update_interval`：多少步下发一次参数（600步 = 60仿真秒）

3. 云端分档逻辑（代码位于 `ca_mp/cloud/cloud_policy.py`）：

| 全局平均压力 | min_green | max_green | base_green |
|-------------|-----------|-----------|------------|
| > 0.8（极高） | 20 | 120 | 45 |
| > 0.4（中档） | 15 | 90 | 35 |
| <= 0.4（常规） | 10 | 90 | 30 |

如需修改分档阈值，编辑 `ca_mp/cloud/cloud_policy.py` 中的 `PRESSURE_TIERS`。

## 示例

让云端更频繁地下发参数（每 30 秒一次）：
```yaml
    cloud_update_interval: 300  # 300步 = 30秒
```

## 常见问题

**Q: 云端协调器是独立进程吗？**
A: 不是。当前实现是单进程内模拟云-边-端协同，CloudPolicy 作为对象注入到 CA-MP 算法中。

**Q: 不用云端协调器可以吗？**
A: 可以。CA-MP 算法在 CloudPolicy 未注入时使用 `config/default.yaml` 中的静态 `base_green` 值。
