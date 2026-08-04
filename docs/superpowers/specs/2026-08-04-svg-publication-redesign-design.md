# ChallengeCup 论文式系统流程图 SVG 重设计规格

> 设计日期：2026-08-04
> 研究基线：docs/notes/svg-publication-style-research.md

## 1. 目标与范围

将仓库中由 Markdown 引用的 5 张架构类 SVG 重新设计为“论文图表 + 系统工程图”风格，使图中的模块、数据流、实验链路和项目状态与当前代码、活跃文档及赛题 PDF 一致。图稿应能在 GitHub Markdown、PDF 截图和黑白打印中保持可读，并让读者能够从图中的文件路径追溯到仓库实现。

正式更新：

- docs/architecture/images/architecture.svg
- docs/architecture/images/simulation-loop.svg
- docs/architecture/images/dependencies.svg
- docs/architecture/images/team-org.svg
- docs/architecture/images/timeline.svg

同步更新仍在使用这些图的活跃 Markdown 说明和替代文本：

- docs/architecture/README.md
- docs/guides/markdown-guide.md
- docs/总路线.md
- docs/tasks/roadmap.md

不修改 Python、SUMO 原始场景、实验产物和接口行为；历史设计稿、任务书和研究笔记不改写成当前状态；浏览器评审临时文件不纳入 Git。

## 2. 设计决策

用户希望图稿偏向论文化和系统化，并已授权由 Codex 自行选择最切合仓库和 PDF 的方案。因此采用以下组合：

- 总架构图使用 C4-inspired 的 system/container/component 层级思想，明确每张图的抽象层级，不把 Python 文件、SUMO 运行时、实验产物和物理路口混成同一层。
- 单次运行图使用简化 BPMN-inspired / UML Activity 风格，明确泳道、步骤编号、循环、终态和证据生成；不声称它是可执行 BPMN 模型。
- 依赖图使用分层 DAG；证据图使用来源链；角色图使用责任矩阵；阶段图使用当前复现/交付门控，不再使用过时的六周甘特日期。
- 采用“白底、深灰文字、深蓝主结构、青绿运行链、棕橙实验/待核验提示”的少色彩系统；不使用渐变、阴影、emoji 或装饰性图标。
- 颜色不是唯一语义通道；编号、边框、位置、文字和线型共同承担信息。
- 所有图保留 SVG 原生 text，并包含 title、desc、role、aria-labelledby 和有意义的 group id；SVG 是可搜索的发布源，不转成单一位图。
- 线型统一为：实线/实心箭头表示同步调用或控制流，实线/开放箭头表示读取/返回数据，虚线表示可选/周期性/延迟关系，点线表示说明或证据来源，点划线表示离线实验/验证/交付流。每张图都有图例。
- 图内节点用 A01、F01、E01 等编号，标题、职责、真实路径分层显示；图注/Markdown alt text 负责解释视角和省略内容。

以上制图规范与 C4、OMG UML/BPMN、W3C SVG/WAI-ARIA/WCAG 的一手资料关系，详见研究笔记；颜色、字号、画布、线宽和具体布局均明确属于本项目设计选择，而非外部强制标准。

## 3. 事实基线

图稿只使用当前仓库可以定位的事实：

1. 赛题 PDF XH-202613_面向雄安新区“城市大脑”的车路云.pdf 要求覆盖仿真环境、车路云协同算法和基准评估全链条，并要求至少 20 个路口、可运行源代码、对比实验和可追溯交付材料。
2. 统一运行链为 RunRequest -> RunService(max_workers=1) -> SceneRegistry -> VariantGenerator -> VariantBundle -> SimulationRunner。
3. SimulationRunner 将 EdgeChannel、BaseControlAlgorithm、TraCIBridge 或 MockBridge 串入每步循环；算法从 JointState 产生 ControlAction，桥接层返回 ActionResult。
4. 当前算法为 fixed_time、actuated、ca_maxpressure；CA-MP 使用 CloudPolicy 的预测/参数下发，并从真实 PhaseTrafficState 选择合法相位。
5. 运行产物按 i{id}/algorithm/x{flow}/s{seed}/{run_id}/ 隔离；精确指标来自 tripinfo.xml，队列指标来自 metrics.csv，汇总写入 summary.json，图表来源由 manifest 记录。
6. PDF 矩阵入口的设计规模为 20 × 3 算法 × 2 流量 × 3 种子 = 360 个组合；图稿只把它标为实验设计/入口，不把已清理的历史产物冒充为当前证据。
7. 当前验收文档明确 Docker live、第二机器复现、Word/PDF 正式报告、PPT 和视频需要独立证据；图稿用 not_run、需重生成、未发现/待交付等文字状态，不用颜色暗示已通过。

## 4. 五张图的内容设计

### 4.1 architecture.svg：统一运行容器架构与 Cloud/Edge/End 映射

使用从左到右的 C4-inspired 容器图：

- 左侧入口：experiments.runner、api.server、scripts/run_pdf_matrix.py。
- 中央应用编排边界：RunService -> SceneRegistry -> VariantGenerator -> SimulationRunner。
- 控制层：fixed_time、actuated、ca_maxpressure；CA-MP 内部关联 CloudPolicy，CloudPolicy 提供 EWMA 预测和参数分档。
- 运行适配层：EdgeChannel、TraCIBridge、MockBridge；SUMO 是外部运行时，MockBridge 是测试替身。
- 右侧证据：RunArtifacts、run_id 目录、metrics.csv、tripinfo.xml、summary.json、run_metadata.json、visualization/manifest。
- 三条淡色映射带只用于解释 PDF 的 Cloud/Edge/End 语境，并标真实仓库组件：Cloud=CloudPolicy，Edge=EdgeChannel/算法，End=Bridge/SUMO。不得使用不存在的 CloudCoordinator、EdgeNode 或网络化多机服务。

### 4.2 simulation-loop.svg：单步仿真控制与证据生成

使用带回边的简化活动/泳道流程：

F01 接收 RunRequest -> F02 创建 VariantBundle 与隔离 RunArtifacts -> F03 启动 TraCIBridge/MockBridge -> F04 读取 JointState -> F05 可选 EdgeChannel send/receive -> F06 CloudPolicy predict/dispatch_params -> F07 algorithm.step() 生成 ControlAction -> F08 action validation/apply_actions() 返回 ActionResult -> F09 simulationStep() -> F10 记录 metrics/events/step log -> 检查 configured_end/exhausted/stopped/disconnected/failed -> 完成后从 tripinfo.xml 和 metrics.csv 生成 summary.json、写 run_metadata.json。

F04-F09 用一条明确回边表示 next simulation step，不能写死为 3600 步。CA-MP 子图按编号显示容量归一化压力、预测修正、下游溢出门控、合法绿灯相位、最小/最大绿灯、安全黄灯/全红过渡、动态时长和 set_phase/set_phase_duration。

### 4.3 dependencies.svg：模块依赖与只读数据边界

使用五层 DAG：

- Input：data/intersection_data/（read-only）、config/default.yaml、SUMO。
- Contracts：core.types、core.run_models、core.config。
- Execution：scenes、engine、algorithms、cloud、ml（optional）。
- Entrypoints：experiments、api、scripts。
- Evidence：metrics.csv、tripinfo.xml、summary.json、visualization、offline manifest。

实线表示代码依赖，虚线表示运行时输入/输出；data/intersection_data/ 旁标只读，output 下的 run_id 旁标每次运行独立写入。禁止画成“仿真 -> CSV -> ML -> 算法 -> 报告”的串行链；ml 标可选扩展，不画成 CloudPolicy 的必经在线模型。

### 4.4 team-org.svg：角色、模块和交付接口

使用三列责任矩阵而非成员编号或会议甘特：

- 契约与仿真：TL 对 core/接口/集成；IA 对场景、20 路口/SUMO 基础；IB 对 engine/api/docker/运行文档。
- 算法与实验：AA 对 FixedTime/Actuated；AB 对 CA-MP/CloudPolicy；EX 对 experiments/visualization/矩阵与指标来源。
- 交付与表达：DA 对 report/Word/PPT/图注；DB 对图表、演示素材和视频。

用箭头表达“契约 -> 算法接入 -> 矩阵验证 -> 报告数字对齐”的接口，附状态栏区分代码/本地验证与待外部核验。不得展示没有仓库证据的成员序号、会议时间、已提交材料或全量完成勾选。

### 4.5 timeline.svg：工程复现与交付阶段

改为当前可审计的阶段门控图：

赛题约束与只读场景 -> 契约与统一入口 -> 本地 SUMO/Mock 与算法验证 -> 矩阵与图表重生成 -> Docker live/第二机器复现 -> 报告/PPT/视频/提交包。

阶段标签分别使用代码/文档、代码/本地证据、需重生成、not_run、未发现或待交付；图例明确 not_run 不等于 pass。矩阵节点显示 20 × 3 × 2 × 3 = 360 的设计规模，不写 360 次已完成，不再保留 7/20 至 8/31 的历史周计划日期。

## 5. Markdown 同步

- 保留 5 个 SVG 文件名和相对路径，避免破坏链接。
- docs/architecture/README.md 只描述实际存在的 SVG，不把不存在的 PNG 备份写成已交付文件。
- docs/guides/markdown-guide.md 的图表目录、示例和说明与新的五张图一致。
- docs/总路线.md 和 docs/tasks/roadmap.md 的架构/循环图 alt text 改为真实主题，并只写当前可验证的运行契约。
- 历史设计/计划内容中的历史图表说明不重写为当前状态。

## 6. 验收标准

1. rg 能找到全部 5 个 SVG 的活跃 Markdown 引用，所有相对链接存在。
2. 5 张 SVG 都是可解析 XML，包含 viewBox、title、desc、role、aria-labelledby、唯一 id/marker，并且无外部图片引用。
3. 图中文字中的类名、路径、算法名、实验规模和状态词均能在源码或活跃文档中找到依据。
4. 图中无 CloudCoordinator、EdgeNode、固定 3600 步、model.pkl 线性链、成员编号、emoji、渐变、阴影或仅凭颜色表达的关键语义。
5. SVG 文本可被 Select-String/XML 解析检索，git diff --check 通过。
6. 浏览器宽屏和窄屏渲染检查确认标题、图例、长路径、中文、箭头和状态标签没有裁切或重叠；必要的截图放在仓库外。
7. 现有文档/链接检查与相关 Python 编译/契约检查通过；报告清楚区分新鲜验证、历史验收证据和未运行外部环境。
8. Git 提交只包含研究笔记、设计规格、实施计划、5 张 SVG 和必要的活跃 Markdown 同步，不包含临时评审页、output 运行产物、源数据或缓存。
