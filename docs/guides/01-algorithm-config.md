# 如何配置算法参数

## 目的

修改信号控制算法的运行参数（绿灯时长、阈值、EWMA 系数等），无需改动代码。

## 前置条件

- 已安装项目依赖：`pip install -e .`
- 了解 YAML 基本语法

## 操作步骤

1. 打开 `config/default.yaml`
2. 定位 `algorithms` 节：

```yaml
algorithms:
  fixed_time:
    use_excel_timing: false    # true=从Excel读配时; false=用SUMO默认

  actuated:
    min_green: 10              # 最小绿灯（秒）
    max_green: 60              # 最大绿灯（秒）
    queue_threshold: 5         # 排队检测阈值（辆）

  ca_maxpressure:
    overflow_occupancy_threshold: 0.9  # 溢出门控触发阈值
    base_green: 30             # 基础绿灯时长（秒）
    min_green: 10
    max_green: 90
    ewma_alpha: 0.3            # EWMA 平滑系数（0~1，越大越敏感）
    prediction_horizon: 300    # 云端预测时域（秒）
    cloud_update_interval: 600 # 云端下发间隔（仿真步，600步=60秒）
```

3. 修改目标参数值
4. 保存文件，重新运行仿真即可生效

## 示例

将 CA-MP 的溢出门控阈值从 0.9 调低到 0.8（更积极地触发门控）：

```yaml
  ca_maxpressure:
    overflow_occupancy_threshold: 0.8
```

运行验证：
```bash
python examples/run_ca_max_pressure.py 16 3600
```

## 常见问题

**Q: 修改后没效果？**
A: 确认修改的是 `config/default.yaml`，不是 `config/` 下其他文件。也可通过环境变量 `CC_DATA_ROOT` 覆盖数据路径，但算法参数只从此文件读取。

**Q: 参数含义不确定？**
A: 参见 `docs/architecture/interface.md` 中 CloudPolicy.dispatch_params 小节的分档表。
