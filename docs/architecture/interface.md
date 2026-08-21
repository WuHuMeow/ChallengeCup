# 架构接口说明

本文聚焦模块边界和数据流。字段级公共契约见
[`docs/interface.md`](../interface.md)。

## 运行架构

```text
CLI / REST API / matrix / verifier
              |
              v
          RunRequest
              |
              v
     RunService (max_workers=1)
        |             |
        |             +--> RunArtifacts + run_id
        v
    SceneRegistry
        |
        v
 VariantGenerator --> VariantBundle
        |
        v
 SimulationRunner
        |
        +--> EdgeChannel (optional delay/filter)
        |
        +--> BaseControlAlgorithm
        |        |
        |        +--> CloudPolicy
        |
        +--> TraCIBridge <--> SUMO
                 |
                 +--> metrics/events/XML/metadata
                              |
                              v
                    experiments.summary
                              |
                              v
                         summary.json
```

所有入口统一走 `RunService`，避免 CLI、API、批量脚本各自实现不同的生命周期。
服务固定单 worker，因为 TraCI Python 客户端包含全局连接状态。

## 隔离与可恢复性

每个请求在执行前创建独立目录：

```text
<root>/i{id}/{algorithm}/x{flow}/s{seed}/{run_id}/
```

运行目录同时包含输入变体、日志、SUMO 原始输出、精确汇总和终态元数据。目录创建使用
`exist_ok=False`，相同路口、算法、流量和种子并发或重复运行也不会互相覆盖。

PDF 矩阵将 `请求键 -> run_id` 写入 `matrix_state.json`。恢复时只有终态为
`completed` 且七类必需产物均非空的运行才会跳过，否则重新生成新的 `run_id`。

## 数据层

### RunRequest / RunResult

`RunRequest` 是运行的唯一输入，包含场景、算法、步数、流量、种子、边缘通道、变体和
CA-MP 参数。`RunResult` 返回 `run_id`、`RunStatus`、原因、运行目录和可选精确汇总。

### JointState

`TraCIBridge.get_state()` 将 SUMO 状态转换为 `JointState`：

- `queues` 提供进口道排队和容量；
- `vehicles` 经过采样并限制为最多 500 辆；
- `arrival_history` 保留最近 300 步；
- `phase_states` 将真实 tlLogic 相位映射到上下游车道、容量、排队和下游占用率。

### PhaseTrafficState

CA-MP 不再从车道名猜相位。每个 `PhaseTrafficState` 都携带真实
`phase_index`、`signal_state`、上下游车道及容量，因此控制输出是 SUMO 可接受的合法整数
相位。

### ActionResult

`SafetyExecutor.apply(actions, state, bridge)` 是唯一的信号动作写入入口，返回与
算法原始请求逐项关联的 `tuple[ActionResult, ...]`。执行器负责最小绿灯、黄灯和全红
时长、60 仿真秒动作有效期、可达清空路径，以及仅限零步/零时刻/零相位已持续时间的
固定配时程序安装；启动程序的每个服务绿灯和循环转换还必须独立满足当前最小绿灯、
配置黄灯和纯全红时长。最小绿灯值在每批动作执行时从算法当前配置读取。只有执行器
可以调用 TraCI bridge 的私有低层写入端。接受和拒绝结果同时进入 `events.csv`，可以直接审计
应用动作数和拒绝动作数；计时拒绝不会被记作非法拓扑转换。

## CA-MP 控制路径

```text
PhaseTrafficState
  -> upstream queue / upstream capacity
  -> downstream queue / downstream capacity
  -> predicted arrivals
  -> downstream overflow gate
  -> select legal green phase
  -> max-green replacement and requested green duration
  -> SafetyExecutor minimum-green guard
  -> SafetyExecutor yellow/all-red transition
  -> private bridge signal sink
```

压力函数为“容量归一化上游压力 - 容量归一化下游压力 + 预测修正”。当下游占用率达到
`overflow_occupancy_threshold` 时，该相位不可选。动态绿灯按选中压力相对平均正压力缩放，
并限制在云端下发的 `min_green` 与 `max_green` 范围内。

校准通过 `experiments/tuning.py` 使用种子 42，种子 123/456 只做留出评估，避免用留出
结果反向选择参数。

## 指标与来源

实时 `metrics.csv` 用于队列统计；运行结束后：

- `tripinfo.xml` 提供行程时间、timeLoss、停车次数、燃油；
- `metrics.csv` 提供平均/最大排队；
- `experiments.summary.write_run_summary()` 写 `summary.json`；
- 缺失的精确量写 JSON `null`，不合成零值。

`summary.json` 同时保存 `run_id` 和来源文件名，图表 manifest 再记录所消费的运行和矩阵，
形成可追溯证据链。

## API 边界

FastAPI 只负责验证模型和转发：

- `/api/runs` 调用 `RunService.submit()`；
- `/api/runs/{run_id}` 和 `/metrics` 读取相同运行记录；
- `/api/cloud/predict` 暴露 `CloudPolicy` 契约；
- `/api/edge/control` 暴露 CA-MP 决策契约。

规范静态文件为：

- `docs/api/openapi.json`
- `docs/api/postman_collection.json`

## 部署边界

Docker 统一入口是：

```text
python3 -m experiments.runner
```

运行参数通过 `docker run` 或 compose command 传入，产物挂载到 `/app/output`。离线包由
`scripts/package_offline.py` 生成，并把 Docker live 与第二机器复现分开记录为
`pass`、`fail` 或 `not_run`。

## 关键不变量

- `data/intersection_data/` 只读；
- 一次运行只写自己的 `run_id` 目录；
- 所有 TraCI 运行经单 worker 串行；
- `set_phase` 必须是合法整数相位；
- 精确指标缺失用 `null`；
- `not_run` 不能写成 `pass`；
- 源数据 SUMO warning 与完成终态同时保留；
- 报告、PPT、视频是独立交付物。
