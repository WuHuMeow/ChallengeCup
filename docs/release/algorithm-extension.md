# 算法扩展指南

## 标准接口

新算法继承 `algorithms/base.py` 的 `BaseControlAlgorithm`（ABC），在每步
收到 `JointState`（路口状态：各进口道排队、容量、当前相位等），返回
`ControlAction`（目标相位与时长）。非法相位、跳变和越权时长会被
`engine/action_validation.py` 与安全执行器拒绝并记录为安全事件。

## 注册

在 `algorithms/registry.py` 注册 canonical 算法 ID；矩阵、REST API 与 Web
控制台均从注册表发现算法。ID 使用小写下划线（如 `my_algorithm`），与
`--algorithm` 参数一致。

## 必须满足的契约

- 合法整数相位：只允许场景 `sumocfg`/`turn.xml` 中定义的相位集合。
- 容量归一化压力（如实现 MaxPressure 类策略）：`pressure = queue / capacity`。
- 下游溢出门控：进口道占用率超阈值时按安全规则强制放行，防止死锁。
- 云端动态绿灯（可选）：经 `cloud/cloud_policy.py` 的 `CloudPolicy` 消息
  信封下发，带 run/time/version/expiry 字段。
- 黄灯/全红过渡由执行器统一保证，算法不得跳过。

## 测试

- 单元：相位合法性、压力计算、门控触发（参考
  `tests/test_algorithms.py`、`tests/test_capacity_aware_max_pressure.py`）。
- 矩阵冒烟：`scripts/run_pdf_matrix.py --profile smoke --algorithm <id>`
  （在允许列表内）。
- 指标与证据：run 目录产物必须满足
  [证据合同](evidence-contract.md)；缺失精确量写 `null`。

## 调参与校准

EWMA/校准链路见 `ml/train.py`；校准与留出种子必须分离，校准种子不得进入
留出评估。调优过程与结论按
[实验协议](experiment-protocol.md) 的统计判定规则报告。
