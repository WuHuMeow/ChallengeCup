# IA/IB 全量闭环设计

## 1. 背景与目标

当前仓库已经包含 20 个路口数据、SUMO/TraCI 基础代码、批量验证脚本、日志组件和部署资料，但仍存在以下 IA/IB 阻塞项：

- `engine/configs/` 的增强版 SUMO 配置沿用扁平化前的相对路径，当前无法启动。
- SUMO 原生产物、指标 CSV、逐步日志和事件日志没有统一的单次运行目录协议。
- 现有验证脚本的输入、输出目录与报告口径不一致。
- EdgeChannel 已有独立实现和单测，但尚未接入 runner 的状态数据流。
- 当前 Python 环境缺少 pytest，Docker 不可用，历史验证记录不能替代本次实测。
- AB 的 CA-MP 仍是 MVI，EX 的正式实验与精确指标尚未完成，不能错误归入 IA/IB 验收。

本设计以竞赛 PDF 的硬要求为基准：提供完整的 20 路口工程、可运行仿真系统、源代码、详细部署说明，并能完整复现典型场景下的管控流程。Docker 属于工程化可选路径，不作为本机 IA 验收的硬门槛。

## 2. 范围与所有权

### 2.1 IA 所有权

IA 负责：

- 20 个路口数据与 metadata 完整性。
- 原始和增强版 SUMO 配置兼容性。
- 配置生成、快速验证、完整验证、输出检查、压力与资源检查脚本。
- SUMO 1.27.1 环境说明和可复现验证报告。
- Dockerfile、Compose、Docker 忽略规则和部署命令的静态一致性。

### 2.2 IB 所有权

IB 负责：

- TraCI 生命周期、状态采集、动作下发、异常关闭与可选重连。
- SimulationRunner 主循环、seed 透传和运行产物协议。
- EdgeChannel 延迟与过滤接入。
- 每步日志、事件日志、SUMO XML 与指标 CSV 的完整输出。
- CloudPolicy 的预测、压力分档、周期下发和历史输入接口。
- engine/cloud 接口文档、部署运行说明及相应测试。

### 2.3 跨角色边界

IA/IB 不代替其他角色完成以下工作：

- TL：最终全项目集成、发布标签、提交与验收签字。
- AA/AB：算法正确性与性能；特别是 CA-MP 三项核心创新和真实预测模型。
- EX：360 次正式实验、精确指标、统计检验和效果结论。
- DA/DB：报告、PPT、正式图表、看板和演示视频。

跨角色未完成项通过契约测试和阻塞记录隔离。IA/IB 可以证明平台能承载符合接口的算法，但不能把无效算法动作或缺失实验结论声明为已通过。

## 3. IA 仿真基础设施设计

### 3.1 配置生成

`scripts/generate_configs.py` 作为增强配置的唯一生成入口。它基于配置文件所在目录计算到原始数据的相对路径，不再写死目录层级。20 个 `engine/configs/demo_N.sumocfg` 由该脚本机械生成，并保留原配置中的步长、路由容错和 queue 输出能力。

原始 `data/intersection_data/` 保持只读；兼容性增强只落在 `engine/configs/`。

### 3.2 数据与配置校验

校验分为三层：

1. 静态完整性：20 个路口各自具备 net、route、flow、sumocfg、turn 和 Excel 文件，metadata 与 edge mapping 覆盖全部路口。
2. 快速运行：原始配置和增强配置各运行 100 步，检查退出码和 `Error:` 输出。
3. 完整运行：增强配置各运行 3600 仿真秒，检查完成状态、运行耗时和 SUMO 输出文件。

验证报告区分 warning 与 error。已有的信号相位 warning 如不导致失败，应保留在报告中，不静默忽略。

### 3.3 压力与资源验证

IA/IB 的压力验证使用可用的 FixedTime 或 Actuated 控制器，覆盖 1.5 倍流量、路口 1/11/16 和长时间运行。CA-MP 的算法效果不作为基础设施通过条件。

资源检查记录 Python 进程峰值、SUMO 子进程退出状态、输出文件大小和运行耗时。阈值失败必须返回非零退出码。

### 3.4 Docker 交付

Dockerfile、Compose 与部署文档必须引用当前扁平目录、完整依赖和有效入口。静态检查覆盖 COPY 路径、入口脚本、数据目录、输出挂载和文档命令。

若环境存在 Docker，则追加 build/run 验证；若不存在，则报告明确记录 `not run: Docker unavailable`，不得写成通过，也不阻塞 PDF 硬要求下的本地部署验收。

## 4. IB 运行时基础设施设计

### 4.1 单次运行产物协议

每次运行使用独立目录，目录名至少编码路口、算法、流量倍率和 seed。目录包含：

- `metrics.csv`
- `simulation_log.csv`
- `events.csv`
- `tripinfo.xml`
- `stats.xml`
- `traj.xml`
- 可选 `queues.xml`
- `run_metadata.json`

`run_metadata.json` 记录参数、开始/结束时间、SUMO 版本、最终状态、退出原因和已生成文件。失败运行也要保存可诊断的 metadata 与已有日志。

### 4.2 TraCI 与输出隔离

TraCIBridge 接收显式运行目录，并在启动命令中覆盖 SUMO 输出路径。任何运行都不得把生成文件写入 `engine/configs/` 或原始数据目录。

启动前校验配置与输出目录；启动失败时关闭残留连接；`close()` 保持幂等。自动重连必须更新内部状态，并保留重连事件，不能假装仿真连续无中断。

### 4.3 状态与消息流

标准数据流为：

1. TraCI 采集 JointState。
2. 可选 EdgeChannel 对状态执行方向过滤和步延迟。
3. 算法消费可用状态并返回 ControlAction。
4. TraCIBridge 校验并应用动作。
5. collector 和 event logger 写入本次运行目录。

默认通道为零延迟，不改变当前本地行为。延迟通道尚未产出状态时，runner 推进仿真但不调用算法，事件日志记录等待状态。

### 4.4 动作与错误处理

动作类型、TLS ID 和值在进入 TraCI 前校验。非法动作记录结构化 `invalid_action` 事件并跳过；未知算法、非法倍率、无效 seed、缺失场景或不可写输出目录在启动 SUMO 前失败。

FatalTraCIError、提前结束和用户中断采用不同的最终状态。所有路径都通过 `finally` 保存已有产物并关闭连接。

### 4.5 CloudPolicy 边界

IB 验证 EWMA 推理、压力分档、更新周期、reset 和历史输入契约。CloudPolicy 是否被 CA-MP 正确用于最终相位决策属于 AB 验收，不由 IB 伪造。

## 5. 验证策略

### 5.1 Python 环境

使用仓库本地 `.venv` 安装运行依赖、pytest 和必要质量工具。验证报告记录实际解释器和依赖版本，避免再次使用缺少 pytest 的 MSYS Python。

### 5.2 自动化测试

测试至少覆盖：

- 配置生成路径和 20 路口静态完整性。
- runner 运行目录命名与产物清单。
- SUMO 输出重定向和并行运行隔离。
- seed 命令透传、同 seed 复现和异 seed 差异。
- EdgeChannel 零延迟、延迟、方向过滤和 runner 集成。
- 非法动作、启动失败、FatalTraCIError、重连与幂等关闭。
- 车辆采样上限、进口道优先、历史窗口和 CloudPolicy 周期下发。
- CLI 参数、错误退出码和帮助文本。
- Docker/Compose 静态路径一致性。

全量命令包括 pytest、compileall、模块导入、Git diff 检查和真实 SUMO 集成验证。

### 5.3 真实 SUMO 验收矩阵

- 20 个原始配置，各 100 步。
- 20 个增强配置，各 100 步。
- 20 个增强配置，各 3600 仿真秒。
- 路口 1、11、16使用 FixedTime 与 Actuated 进行 runner 闭环。
- 路口 1、11、16执行 1.5 倍流量和资源检查。
- CA-MP 只执行接口兼容检查；若仍输出非法相位值，报告归属 AB 阻塞项。

## 6. 文档与证据

完成时更新：

- `docs/reports/ia-ib-final-verification.md`
- `docs/deployment.md`
- `docs/interface.md`
- `scripts/README.md`
- `README.md` 的分工状态
- `docs/reports/w6-review-issues.md`

最终验证报告逐条列出命令、退出码、耗时、结果、warning 和环境限制。历史报告只作对照，不替代新结果。

## 7. 临时文件与清理策略

所有测试和实跑产物写入唯一的隔离目录。自动化测试优先使用 pytest 的临时目录；真实 SUMO 验证使用 `output/verification/<run-id>/`。

验证结束后：

1. 保留最终验证报告和明确列为验收证据的摘要。
2. 删除本次工作生成但未被报告引用的临时 XML、CSV、日志、缓存和中间变体。
3. 删除意外落入源码、配置或原始数据目录的运行产物。
4. 扫描 `__pycache__`、`.pytest_cache`、临时图片、临时 PDF、编辑器备份和零字节文件。
5. 运行 `git status --short`，确认没有无关文件或未说明的修改。

清理只针对本次工作明确生成的文件。已有用户文件、历史实验结果和无法确认来源的未跟踪文件不得删除。

## 8. 完成定义

IA 完成需满足：20 路口数据完整，原始和增强配置可运行，完整验证通过，压力与资源检查通过，部署与 Docker 静态资料一致，限制如实记录。

IB 完成需满足：runner/TraCI/EdgeChannel/日志/seed/异常处理形成闭环，自动化测试和真实 SUMO 集成通过，接口与部署文档和代码一致。

IA/IB 完成不等于全项目完成。以下事项仍由对应角色关闭后才能进入最终发布：CA-MP 核心算法、真实 ML、正式实验与精确指标、报告/PPT/视频、全员 review、`v1.0-final` 和提交回执。
