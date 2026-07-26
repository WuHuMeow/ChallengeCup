# IA/IB PDF 对齐完成设计

## 1. 目标

在现有 `main` 分支上完成 IA、IB 第 1–6 周全部职责，并补齐直接阻塞其验收的跨角色依赖，使仓库能够真实支撑比赛 PDF 中的：

- 功能一：智能交通协同管控算法的抽象设计、接口、实现与可视化验证；
- 功能二：20 路口高保真仿真平台、模块集成及部署；
- 功能三赛道 B：经典交通管控算法在雄安“窄路密网”场景中的适配、调优和性能评估。

本设计的完成对象是 IA、IB 及其直接依赖，不把最终报告、答辩 PPT、5–8 分钟视频、报名提交或官方回执伪装成 IA/IB 工作。

## 2. PDF 验收映射

| PDF 要求 | 本设计中的实现 |
|---|---|
| 至少 20 个路口的完整仿真工程 | 保留并校验 20 路口原始场景，生成可运行的增强配置 |
| 场景参数化和扰动注入 | 支持流量倍数、车辆类型、信号方案以及车道/道路封闭等变体 |
| 车—路—云数据流和 API | 统一 `JointState`、`PredictionResult`、`ControlAction`，提供 OpenAPI 与 Postman/Apifox 集合 |
| 一种控制策略集成并与固定配时对比 | 完成 CA-MP，统一接入 Runner，并与 FixedTime、Actuated 对比 |
| 轻量化智能决策模型 | 使用现有轻量预测策略为 CA-MP 提供可选到达流预测，不引入必须训练的大模型 |
| 通信模拟、数据采集或算法适配器 | 完成 EdgeChannel、RunArtifacts、算法插件接口和指标采集 |
| 容器化或性能优化 | 完成 Docker 交付、资源压力测试和离线包；实时 Docker 验证按环境如实记录 |
| 多场景、多参数、基线实验 | 执行 20 路口 × 2 流量 × 3 算法 × 3 种子，共 360 次标准实验 |
| 平均行程时间、排队、通行能力、油耗等指标 | 从 SUMO 原生 XML 和运行状态计算，禁止固定值或占位值 |
| 可视化证据 | 生成轨迹图、指标曲线、对比图和路口热力图 |
| 完整部署运行说明 | 文档中的命令、参数、输出目录与实际代码保持一致 |

## 3. 范围

### 3.1 IA 职责

IA 负责：

- 20 路口原始数据、元数据和 SUMO 配置完整性；
- 原始配置、增强配置和变体配置的生成与校验；
- 流量、车辆类型、信号方案和扰动事件的参数化注入；
- SUMO 本地环境、Docker、Compose、离线镜像和跨机器复现说明；
- 原始/增强场景的完整运行、压力和资源验证；
- 打包清单、部署命令和验证证据。

原始 `data/intersection_data/` 只读。任何增强配置、变体和运行输出均写入派生目录，不修改原始赛题数据。

### 3.2 IB 职责

IB 负责：

- TraCI 连接、推进、状态采集、动作应用、重连和关闭；
- EdgeChannel 延迟、过滤和等待语义；
- `SimulationRunner` 的统一控制循环；
- 单次、批量和 API 入口共用的 RunService；
- `RunArtifacts`、逐步日志、事件日志、SUMO XML 和终态元数据；
- API 的真实运行、状态、指标、云预测和边缘控制接口；
- OpenAPI、Postman/Apifox 集合和接口契约测试；
- 异常恢复、终态区分和可审计性。

### 3.3 纳入的直接跨角色依赖

以下工作虽然原属其他角色，但直接阻塞 IA/IB 与 PDF 的有效验收，因此纳入：

- AB：完成 CA-MP 的容量归一化压力、溢出门控、动态绿灯和合法相位逻辑；
- EX：完成真实指标计算、参数调优和基线实验；
- DB：替换热力图占位实现，生成验收所需的标准图表。

### 3.4 不在本设计中的最终交付

- 系统设计与算法报告的最终排版和完整文字结论；
- 答辩 PPT；
- 5–8 分钟演示视频、配音和剪辑；
- 比赛报名、邮件提交、官方验收和获奖结果。

这些工作必须在项目总进度中单独跟踪。

## 4. 总体架构

所有入口使用同一条运行链：

```text
CLI / Batch / REST API
        |
        v
RunService + RunRequest
        |
        v
SceneRegistry / VariantGenerator / RunArtifacts
        |
        v
SimulationRunner
        |
        +--> TraCIBridge --> SUMO
        |
        +--> JointState --> EdgeChannel --> CloudPolicy --> Algorithm
                                                      |
                                                      v
                                               ControlAction[]
        |
        v
动作校验与应用 --> events / logs / XML / metrics / metadata
        |
        v
精确指标汇总 --> 图表与验收报告
```

CLI、批量实验和 API 只负责请求解析与结果展示，不得自行维护另一套运行状态、输出目录或日志语义。

## 5. 组件职责

### 5.1 场景与变体

`SceneRegistry` 是 20 路口清单的唯一来源。`VariantGenerator` 在每次运行目录内生成派生输入，至少支持：

- 流量倍数 `1.0` 和 `1.5`；
- 可配置车辆类型比例；
- 可覆盖的初始信号方案；
- 一个可复现的施工占道或道路封闭扰动。

生成器返回新增 SUMO 文件列表，由 TraCI 启动命令显式加载。相同输入参数和种子必须得到相同变体。

### 5.2 TraCI 与 EdgeChannel

TraCI 每步先生成原始 `JointState`。原始状态用于指标和日志；经过 EdgeChannel 的控制状态用于算法决策。延迟通道尚未输出状态时，SUMO 可以继续推进，但算法不得使用未来状态。

动作进入 SUMO 前统一校验：

- `tls_id` 必须存在；
- `action_type` 必须受支持；
- 相位索引和时长必须合法；
- 目标相位必须符合当前信号程序。

被拒绝的动作只记录为 `action_rejected`，不得同时记录为成功动作。

### 5.3 CA-MP

CA-MP 的相位压力使用车道容量归一化：

```text
phase_pressure =
sum(incoming_queue / incoming_capacity)
- sum(outgoing_queue / outgoing_capacity)
```

设计包含：

- 容量未知时使用明确、可配置的安全默认值；
- 当下游占用率超过阈值时启用溢出门控；
- 遵守最小绿、最大绿、黄灯和全红约束；
- 根据当前相位压力、候选相位压力差和预测到达量决定保持、延长或切换；
- 只输出当前场景存在的合法相位；
- 所有阈值进入配置、metadata 和调参记录。

调参使用路口 1、11、16、种子 42、流量 `1.0/1.5` 作为校准集。参数冻结后，种子 123、456 和全部 20 路口作为主要留出评估集，避免用同一批结果同时调参和宣称提升。

### 5.4 RunService

`RunService` 统一处理：

- `RunRequest` 校验；
- `run_id` 分配；
- 场景和算法实例创建；
- 单次运行、批量运行和 API 后台任务；
- 停止信号；
- 状态查询；
- `RunResult` 组装。

批量实验必须逐次调用 RunService，不能绕过 `RunArtifacts`。

### 5.5 指标与可视化

指标来源固定为：

- 平均行程时间：`tripinfo.duration`；
- 平均延误：`tripinfo.timeLoss`；
- 排队长度：逐步 `JointState.queues` 或 `queues.xml`；
- 通行能力：完成到达车辆数和单位时间吞吐；
- 停车次数：`tripinfo.waitingCount` 或等价 SUMO 字段；
- 燃油消耗：SUMO 排放/行程输出中的燃油字段。

缺少数据时必须报告 `missing` 和原因，不得写成 `0.0`。

标准图表至少包括：

- FixedTime、Actuated、CA-MP 指标对比图；
- 指标随时间变化曲线；
- 典型路口排队或拥堵热力图；
- 至少一个典型场景的时空轨迹图；
- 每张图对应的运行参数、数据文件和生成命令。

## 6. 数据与接口契约

### 6.1 共享类型

`RunRequest` 包含：

- `intersection_id`
- `algorithm`
- `steps` 或目标仿真时长
- `flow_multiplier`
- `seed`
- `output_root`
- 可选 EdgeChannel 延迟、方向过滤参数
- 可选扰动配置

运行时继续使用 `JointState`、`PredictionResult` 和 `ControlAction`。新增 `RunResult` 统一返回 `run_id`、状态、原因、目录、指标摘要、时间和文件清单。

### 6.2 API

规范端点为：

- `GET /api/health`
- `GET /api/scenes`
- `POST /api/runs`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/metrics`
- `POST /api/runs/{run_id}/stop`
- `POST /api/cloud/predict`
- `POST /api/edge/control`

旧根路径或重复 `/api/simulation/*` 端点只允许作为薄兼容包装，必须转发到 RunService，并在 OpenAPI 中标记 deprecated。API 不得维护与 `run_metadata.json` 不一致的第二份业务状态。

仓库交付：

- 自动生成的 OpenAPI 规范；
- 可导入 Postman/Apifox 的 collection；
- 本地环境变量示例；
- 成功、参数错误、未知场景、未知算法、运行失败和停止请求断言。

### 6.3 运行目录

每次运行使用：

```text
output/runs/
  i{intersection}/
    {algorithm}/
      x{flow_multiplier}/
        s{seed}/
          {run_id}/
            run_metadata.json
            metrics.csv
            simulation_log.csv
            events.csv
            tripinfo.xml
            stats.xml
            traj.xml
            queues.xml
            summary.json
            figures/
```

`run_id` 防止同一组参数重复运行时相互覆盖。成功运行的核心文件必须存在且非空；`queues.xml` 仅在配置启用时要求存在。失败运行可以缺少尚未生成的文件，但 metadata 必须逐项记录原因。

## 7. 错误处理和终态

启动 SUMO 前校验场景、算法、步数、种子、流量倍数、输出目录和依赖环境。预检失败不创建 SUMO 子进程，但仍返回结构化错误。

终态固定为：

| 状态 | 含义 |
|---|---|
| `queued` | API 任务已接受但尚未执行 |
| `running` | SUMO 已启动并正在推进 |
| `completed` | 达到请求的目标仿真时长并正常保存 |
| `stopped` | 收到用户停止请求并完成安全关闭 |
| `ended_early` | SUMO 在目标时长前正常退出 |
| `disconnected` | TraCI 连接在有限重试后仍无法恢复 |
| `interrupted` | 进程收到键盘或系统中断 |
| `failed` | 其他未恢复异常 |

规则：

- 重连开始、成功、失败均写入 `events.csv`；
- 重连后重新读取状态，不假装中断期间连续运行；
- 每次运行只写一个最终终态事件；
- 所有路径都在 `finally` 中关闭连接并保存已有产物；
- metadata 采用临时文件加原子替换；
- 失败运行保留诊断证据；
- 外部验证未执行时使用 `not_run`，不能写成 `pass`。

## 8. 测试与验收

### 8.1 自动化质量门

- 全部 Python 测试通过；
- `compileall` 通过；
- 项目包导入通过；
- lint/格式和 `git diff --check` 通过；
- 工作区只包含本任务的预期文件；
- 文档命令、路径和输出契约测试通过。

### 8.2 IA 验收

- 20 个原始场景静态完整；
- 20 个原始配置快速运行；
- 20 个增强配置快速运行；
- 20 个增强配置运行到 3600 仿真秒；
- 变体生成覆盖流量、车辆、信号和扰动；
- 路口 1、11、16 在 `1.5` 倍流量下完成压力和资源测试；
- Dockerfile、Compose、挂载和入口静态检查通过；
- Docker 可用时完成 build、run、save、load；
- 第二台机器可用时完成离线包复现并保留机器、命令、镜像摘要和结果。

### 8.3 IB 验收

- TraCI 生命周期、幂等关闭和异常清理；
- EdgeChannel 零延迟、延迟、过滤和等待；
- 合法动作与拒绝动作分离；
- 重连事件和 `disconnected` 终态；
- 正常、停止、提前结束、中断和失败终态；
- 单次和批量运行均生成完整 RunArtifacts；
- API 端点调用真实 RunService；
- OpenAPI 与 Postman/Apifox 契约断言；
- 同参数重复运行不覆盖；
- 并行运行目录和连接互相隔离。

### 8.4 PDF 和赛道 B 验收

正式矩阵为：

```text
20 路口 × 2 流量等级 × 3 算法 × 3 种子 = 360 次
```

算法为 FixedTime、Actuated、CA-MP；流量为 `1.0`、`1.5`；种子为 42、123、456。每次覆盖 3600 仿真秒；如果 SUMO 步长为 0.1 秒，则 Runner 需要 36000 个控制步。

每次运行必须：

- 有明确终态；
- 生成完整核心产物；
- 指标非占位；
- 失败时进入失败清单而不是从汇总中静默删除。

留出评估单独报告种子 123、456 的结果。CA-MP 相对于 FixedTime 的提升必须同时给出绝对值、百分比、样本数和失败数，不允许只挑选有利场景。

### 8.5 完成度口径

最终报告分开记录：

1. 仓库实现完成度；
2. 自动化验证完成度；
3. 本机 SUMO 验证完成度；
4. Docker 实时验证完成度；
5. 第二台机器复现完成度。

只有五项均有实际通过证据时，IA/IB 才标记为 `100% verified`。若 Docker 或第二台机器不可用，只能标记为 `code complete, external validation pending`。

## 9. 文档与证据

实现完成后更新：

- `README.md`
- `docs/interface.md` 及当前规范位置
- `docs/deployment.md` 及当前运维位置
- `scripts/README.md`
- `tests/README.md`
- `docs/reports/ia-ib-final-verification.md`
- `docs/reports/batch-validation-report.md`
- OpenAPI 和 Postman/Apifox 文件

验证报告逐项记录命令、环境、版本、耗时、退出码、警告、错误和证据路径。历史报告只能用于对照，不能替代本次运行。

## 10. 实施约束

- 以测试驱动方式修改行为；
- 优先复用现有 `RunArtifacts`、Runner、Bridge、SceneRegistry 和配置模式；
- 不进行与 IA/IB、直接阻塞依赖无关的重构；
- 不修改或删除无法确认来源的用户文件和历史结果；
- 临时产物写入隔离目录；
- 任何完成声明前重新运行相应验收命令；
- 设计批准后先编写实施计划，再开始修改实现代码。
