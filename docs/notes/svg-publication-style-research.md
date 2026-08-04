# 静态 SVG 论文制图与系统流程图研究基线

> 研究日期：2026-08-04
>
> 本文是 `docs/notes/` 下的非规范技术调研记录。它把公开的一手规范与本仓库的制图建议分开：标为“来源明确要求”的内容是对官方资料的保守转述；标为“本仓库设计选择”的内容是为了让本项目的静态 SVG 适合论文、评审、灰度打印和代码审计而提出的可执行约定，不应冒充 UML、BPMN、ArchiMate 或 SVG 的强制语义。

## 1. 结论先行

本仓库适合采用“分层架构图 + 单独的运行流程图 + 证据/产物图”三类图，而不是把所有模块、算法、SUMO 过程和实验文件塞进一张图：

1. **系统架构图**采用 C4 的层级思想，建议以 Container/Component 两个视图为主。主图展示 `RunService`、`SceneRegistry`、`VariantGenerator`、`SimulationRunner`、`CloudPolicy`、三种算法、`TraCIBridge`/`MockBridge`、SUMO 和实验产物；代码文件路径放在节点副标签中或图注中。
2. **运行流程图**采用 BPMN 或 UML Activity 的语义之一，并在图例中明确是哪一种。建议用泳道表示“调用者 / RunService / 场景与变体 / SimulationRunner / 算法与 CloudPolicy / Bridge 与 SUMO / 产物”，用编号表示一个请求从提交到 `summary.json` 的顺序。
3. **证据与产物图**不强行套 BPMN。它只表达“输入、运行目录、原始 SUMO 输出、指标、`summary.json`、批量汇总”的来源链，所有虚线、文件图标和箭头都必须配图例。
4. 所有静态 SVG 都应含有可读的 `<title>` 和 `<desc>`；正文标签尽可能保留为 SVG 文本；颜色不能是唯一编码通道；图注必须说明图的视角、范围、来源文件和生成/复核日期。
5. “规范形状”与“本仓库自定义视觉编码”必须分开。若使用 BPMN/UML 形状，就使用其标准语义；若使用 C4 风格或自定义模块盒，就在图例中声明“C4-inspired / repository notation”，不要把自定义箭头称为 BPMN Sequence Flow。

## 2. 本仓库事实：图应当画什么

以下结论来自当前工作树的真实文件，而不是根据模块名称推测：

| 真实路径 | 已核实职责 | 适合在图中的表达 |
| --- | --- | --- |
| `engine/run_service.py` | `RunService` 是统一编排入口；`ALGORITHM_FACTORIES` 注册 `fixed_time`、`actuated`、`ca_maxpressure`；提交时创建隔离产物目录，执行时依次取得场景、生成变体、创建算法和 `SimulationRunner`，最后从 metadata/summary 生成 `RunResult`。 | 架构图的核心服务；流程图的主控制节点。 |
| `scenes/registry.py` | `SceneRegistry` 提供路口场景查找。 | 场景注册/解析模块，不应画成 SUMO 本身。 |
| `scenes/variant.py` | `VariantGenerator` 根据场景元数据、流量倍数和变体请求生成 `VariantBundle` 及附加文件。 | 输入变体生成模块；输出连到 runner，而不是直接连到算法。 |
| `engine/runner.py` | `SimulationRunner` 承担一次仿真运行，接收 scene、algorithm、additional files、seed、artifacts 和可选 `EdgeChannel`。 | 运行时边界；可与算法层、Bridge 层分层展示。 |
| `algorithms/fixed_time.py` | `FixedTimeAlgorithm` 是固定配时控制实现。 | 与另外两个算法并列，不能画成 `CloudPolicy` 的子类。 |
| `algorithms/rule_adaptive.py` | `RuleAdaptiveAlgorithm` 是规则/感应式控制实现。 | 与固定配时、CA-MP 并列的算法分支。 |
| `algorithms/ca_max_pressure.py` | `CAMaxPressureAlgorithm` 使用相位交通状态、上/下游压力、预测到达和绿灯约束，产生合法控制动作；文件内还依赖 `CloudPolicy`。 | 算法层的详细图或 CA-MP 专图；不要把“压力计算”误画成 SUMO 内部模块。 |
| `cloud/cloud_policy.py` | `CloudPolicy` 提供云端参数/预测策略；它是 CA-MP 控制路径的一部分。 | 画在控制策略边界内，标注“参数/预测”，不要画成独立仿真引擎。 |
| `engine/traci_bridge.py` | `TraCIBridge` 是实时 SUMO/TraCI 桥接，读取状态并应用动作。 | 外部运行时适配器；箭头要区分“读取状态”和“下发动作”。 |
| `engine/mock_bridge.py` | `MockBridge` 是可替代真实 TraCI 的测试桥。 | 与 `TraCIBridge` 并列为实现/测试替身，不能和 SUMO 同画成两个真实仿真器。 |
| `experiments/runner.py` | `run_batch()` 组合路口、算法、流量等级和种子，默认覆盖 20 个路口、3 种算法、多个流量等级和 `[42, 123, 456]` 种子；单次运行仍交给 `RunService`。 | 实验编排图；用矩阵/重复执行符号，不在主架构图展开 360 个实例。 |
| `experiments/summary.py` | `write_run_summary()` 从 `tripinfo.xml` 和 metrics CSV 生成带 `run_id`、指标和来源文件的 `summary.json`；缺失精确值使用 `null`，不合成零。 | 证据/产物图必须画出来源边，不能把 summary 画成无来源的最终数字。 |
| `engine/artifacts.py`、`output/README.md`、`output/evidence/README.md` | 运行产物按 `run_id` 隔离；`output/` 是可丢弃的运行时根目录，历史矩阵产物已清理，当前不能声称这些生成目录仍然存在。 | 图中画“产物类型/目录契约”，不要把当前不存在的历史目录画成已交付文件。 |
| `docs/architecture/README.md`、`docs/architecture/images/` | 架构图目录已有 SVG 与部分 PNG；当前约定是 SVG 首选，PNG 作为不支持 SVG 的查看器兼容副本。 | 新图应放在已有架构图目录并同步兼容副本（这是后续实现建议；本文本身不修改这些图）。 |

### 2.1 推荐的真实数据流

```text
CLI / REST API / batch experiment
              |
              v
          RunRequest
              |
              v
          RunService
          /       \
 SceneRegistry   RunArtifacts
      |              |
      v              |
 VariantGenerator   |
      |              |
      +------> SimulationRunner <------ algorithm factory
                    |                         |
                    |                         +--> fixed_time
                    |                         +--> actuated
                    |                         +--> ca_maxpressure --> CloudPolicy
                    v
             TraCIBridge / MockBridge <--> SUMO
                    |
                    v
       tripinfo.xml + metrics.csv + metadata + events
                    |
                    v
             experiments.summary
                    |
                    v
               summary.json
```

这是“本仓库事实的概念图”，不是新增的运行时设计。正式 SVG 应将每条关系改为有方向、有标签的边，并对 `MockBridge` 标注“test substitute”。

## 3. 一手来源与可直接采用的规范结论

访问日期均为 **2026-08-04**。规范页面的版本状态很重要：W3C SVG 2 页面显示为 Candidate Recommendation，SVG-AAM 页面显示为 Working Draft 且明确提示仍有过时信息和错误；因此本文对 SVG-AAM 只采用其“映射/可访问性关注点”这一层的指导，不把工作草案的全部条文写成稳定强制要求。

### 3.1 C4：先定抽象层级，再定图的读者

**来源明确要求/定义。** C4 官方资料把核心抽象定义为 software system、container、component、code，并对应 system context、container、component、code 四类静态结构图；官方还列出 system landscape、dynamic、deployment 三类支持图。官方强调 C4 是 notation-independent、tooling-independent，并指出不必机械使用四个层级，系统上下文图和容器图对多数团队已足够。

来源：

- [C4 Model 官方主页](https://c4model.com/)（访问 2026-08-04）
- [C4 Model 官方 Diagrams](https://c4model.com/diagrams)（访问 2026-08-04）
- [C4 Model 官方 Abstractions](https://c4model.com/abstractions)（访问 2026-08-04）

**本仓库设计选择。**

- 论文总览图使用 C4-like 的 system/container 视角：外部参与者是 CLI、REST API、SUMO；系统内部按 `RunService`、场景/变体、运行时控制、产物汇总分组。
- 详细图再下钻到 component 视角：`SceneRegistry`、`VariantGenerator`、`SimulationRunner`、算法工厂、三种算法、`CloudPolicy`、`TraCIBridge`/`MockBridge`。
- 不在一张图同时混用“软件系统、Python 类、输出文件、路口物理信号相位”四个抽象层级。跨层连接必须通过边界节点或拆成第二张图，并在标题中写清视角。
- C4 不规定本仓库的颜色、字体、箭头粗细或 SVG 元素；这些全部由本文第 6 节的仓库基线规定。

### 3.2 UML：当图表达软件结构或控制/活动语义时使用 UML 名称

**来源明确要求/定义。** OMG 的 UML 2.5.1 官方页面将 UML 定义为用于可视化、指定、构造和记录分布式对象系统工件的图形语言，并提供正式规范 PDF 和机器可读模型。由此，若图中使用“UML Activity Diagram”“UML Component Diagram”等名称，图形元素、连接和含义应以 UML 规范为准，而不能仅借用几个圆角矩形就宣称是 UML。

来源：

- [OMG UML 2.5.1 官方规格页](https://www.omg.org/spec/UML/2.5.1/)（访问 2026-08-04）
- [OMG UML 2.5.1 正式 PDF](https://www.omg.org/spec/UML/2.5.1/PDF)（访问 2026-08-04）

**本仓库设计选择。** 运行时步骤可画成 UML Activity 风格，但标题写“运行流程（UML Activity-inspired）”除非已经逐项遵循规范并经过模型审查。流程节点至少要能对应到真实调用：提交/校验、创建隔离产物、查场景、生成变体、构造算法和 runner、TraCI/SUMO 循环、写 metadata/summary。不要用 UML 的对象/组件符号表达不存在的类继承或部署关系。

### 3.3 BPMN：泳道和消息边界适合运行流程，但不能和自定义箭头混称

**来源明确要求/定义。** OMG BPMN 2.0.2 官方页面说明 BPMN 面向设计、管理和实现业务流程的利益相关者，同时要精确到可以转换为软件流程组件；它提供类似流程图、独立于具体实现环境的记法。BPMN 的正式规范页提供 PDF、BPMNDI 和 XML Schema 等正式/机器可读文件。

来源：

- [OMG BPMN 2.0.2 官方规格页](https://www.omg.org/spec/BPMN/2.0.2/)（访问 2026-08-04）
- [OMG BPMN 2.0.2 正式 PDF](https://www.omg.org/spec/BPMN/2.0.2/PDF)（访问 2026-08-04）

**来源语义在本仓库的落地。** 若采用 BPMN 术语，应保留以下区分：一个参与者/协作边界用 pool；同一参与者内部的职责分区可用 lane；同一流程内的步骤使用 sequence flow；跨参与者的消息使用 message flow；关联说明使用 association。不能把“读取 SUMO 状态”“控制动作”“文件产物”全部画成同一种 BPMN 流。

**本仓库设计选择。** 对论文读者，建议采用简化泳道图而不是完整业务 BPMN：泳道只保留调用责任，节点标签同时写 Python 模块路径；若省略 BPMN 事件、网关或消息语义，应在图注中说“简化 BPMN-inspired 流程图”，不要声称该图是可执行 BPMN 模型。

### 3.4 ArchiMate：适合组织/业务/应用/技术层，但不是本仓库第一选择

**来源明确要求/定义。** ArchiMate 是 OMG 的企业架构建模规范，适合用明确的层、元素和关系描述企业架构。本文本轮未继续检索 ArchiMate 官方页面，因此不把具体颜色、形状、关系线含义转述为已核实条款；需要正式采用 ArchiMate 时应直接以 OMG 当前规格页和对应版本 PDF 复核。

来源入口（版本应在绘图前确认）：

- [OMG ArchiMate 官方规格入口](https://www.omg.org/archimate/)（访问 2026-08-04）

**本仓库设计选择。** 本项目当前问题是运行架构和实验产物可追溯性，不是企业架构治理；因此不建议在论文主图中混入 ArchiMate 记法。若未来需要说明“云策略—边缘控制—仿真基础设施”的组织/技术层，可单独做 ArchiMate 图并保持独立图例。

### 3.5 W3C SVG：矢量、可缩放、可独立或嵌入；输出要保留可读结构

**来源明确要求/定义。** W3C SVG 2 将 SVG 定义为基于 XML 的二维矢量和混合矢量/栅格图形语言，内容可样式化、可缩放到不同显示分辨率，可独立查看或嵌入 HTML；这支持本仓库以 SVG 作为论文图源、以 PNG 作为兼容副本的做法。

来源：

- [W3C SVG 2](https://www.w3.org/TR/SVG2/)（访问 2026-08-04）
- [W3C SVG 2 Text](https://www.w3.org/TR/SVG2/text.html)（访问 2026-08-04）

**来源明确的可访问性方向。** SVG 的 `title` 和 `desc` 元素是标准结构元素，可为图形提供标题和描述；SVG-AAM 说明用户代理需要把 SVG 标记映射到平台可访问性 API，并讨论可访问名称、描述、角色、状态、属性以及键盘焦点。SVG-AAM 当前页面明确标注为 Working Draft，并提醒内容可能过时，因此应将其作为实现指导并在目标查看器/辅助技术上测试。

来源：

- [W3C SVG 1.1：Description and Title Elements](https://www.w3.org/TR/SVG11/struct.html#DescriptionAndTitleElements)（访问 2026-08-04）
- [W3C SVG Accessibility API Mappings](https://www.w3.org/TR/svg-aam-1.0/)（访问 2026-08-04；页面状态为 Working Draft，并含不应直接实现的警告）
- [W3C WAI-ARIA 1.2](https://www.w3.org/TR/wai-aria-1.2/)（访问 2026-08-04）

**本仓库设计选择。** 每幅静态图使用如下最小结构（示意，不要求所有图都成为交互组件）：

```xml
<svg xmlns="http://www.w3.org/2000/svg"
     viewBox="0 0 1200 760"
     role="img"
     aria-labelledby="fig-title fig-desc">
  <title id="fig-title">RunService 仿真运行架构</title>
  <desc id="fig-desc">图示 RunService 如何通过 SceneRegistry、VariantGenerator 和 SimulationRunner ...</desc>
  <!-- visible vector shapes and text -->
</svg>
```

`role`、`aria-labelledby`、分组 id、可见标签和 `<desc>` 的具体组合要根据“整幅图作为一张图片”还是“图中对象可逐个访问”来选；本仓库的论文静态图默认把整幅图作为图片，避免制造伪交互控件。

SVG 适合矢量输出，但“把文字转为 path”不是 W3C 的出版强制要求。**本仓库设计选择**是：保留正文和节点标签为 `<text>`，使用稳定字体栈并在发布环境检查字体替换；只有在确定打印环境无法提供字体、且另有可访问/可搜索源文件时，才考虑对最终副本进行轮廓化。保留文本有利于复制、搜索和辅助技术；轮廓化只解决几何确定性，不能替代可访问描述。

## 4. 严谨制图的通用基线：规范与设计选择分开

### 4.1 分层、泳道、模块边界

**来源明确要求/适用范围。** C4 要求先明确抽象层级和图的叙事视角；BPMN/UML 只在使用其正式记法时赋予 pool/lane、activity、component 等术语标准含义。它们都不规定本仓库的具体版式。

**本仓库设计选择。**

- 用大边界表示“责任或部署边界”，边界标题必须是名词：`Application orchestration`、`Control algorithms`、`Simulation adapter`、`Generated run artifacts`。
- 用泳道表示“谁负责当前步骤”，不要用泳道同时表示 Python 包、进程、组织和物理设备。若这四种维度都重要，拆成多张图。
- 同一层级的盒子使用同一宽度/内边距/标题样式；子模块不随意嵌套到另一层级。节点内最多三行：名称、职责、实际路径/接口。
- `SUMO` 画作外部运行时；`TraCIBridge`/`MockBridge` 画作适配器；三种算法画作策略实现；`CloudPolicy` 只放在实际调用它的 CA-MP 路径旁。
- 图上不要将“20 个路口 × 流量等级 × 3 算法 × 3 种子”展开成大量节点；用矩阵注释和 `experiments/runner.py::run_batch` 表达重复维度。

### 4.2 箭头和线型语义

**来源明确要求/适用范围。** UML、BPMN 各自定义自己的连接类型和语义；BPMN 的 sequence flow、message flow、association 不能随意互换。若不完整遵循正式语言，应避免使用会让读者误判的正式术语。

**本仓库设计选择：每种线型只表达一个含义，并在图例重复一次。**

| 视觉编码 | 本仓库语义 | 示例 |
| --- | --- | --- |
| 实线、实心箭头 | 同步调用/控制流 | `RunService → SceneRegistry: get_scene()` |
| 实线、开放箭头 | 数据读取/返回值 | `TraCIBridge → SimulationRunner: JointState` |
| 虚线、开放箭头 | 可选、异步或观察性关系；必须加标签 | `RunService - - > RunArtifacts: metadata/summary` |
| 点线 | 仅说明/归属/来源，不表示执行顺序 | `summary.json ... tripinfo.xml, metrics.csv` |
| 粗边界线 | 模块、进程或外部系统边界 | `Control algorithms` / `SUMO` |

不要同时用箭头颜色和线型表达同一个概念；不要用“粗线”表示高优先级而不写图例。对于 BPMN 图，保留 BPMN 自己的线型并把本仓库的自定义数据来源边另行标注。

### 4.3 编号、图例和标签

**本仓库设计选择。**

- 流程步骤用 `F01`、`F02`…；架构节点用 `A01`、`A02`…；证据产物用 `E01`、`E02`…。编号在一幅图内唯一，不能用颜色代替编号。
- 每个节点首先写用户可读名称，再写短职责，最后写实际路径，例如 `A03 SimulationRunner / engine/runner.py`。
- 所有非直觉颜色、线型、边框、图标和缩写都进入图例；图例不是装饰，应能让读者在没有正文的情况下解码图。
- 编号只标识图中对象，不伪装成 Python 行号、实验 run id 或 UML 元素 id。run id 和文件名应放在产物节点或图注中。
- 图注至少包含：图号、短标题、图的视角/范围、关键假设、来源文件、SVG/PNG 生成日期或 commit。正文应以图注解释“该图省略了什么”。

### 4.4 字体、字号、标题和文件路径

**规范状态。** W3C 规定 SVG 文本是图形语言的一部分，但没有为论文图规定统一字号、字体家族或图注格式；C4 也不规定这些排版参数。论文出版社的具体模板仍应优先于本仓库默认值。

**本仓库设计选择（发布前可调整）。**

- 字体栈优先使用 `Arial, "Noto Sans CJK SC", sans-serif` 或项目发布环境明确安装的等价字体；中英文混排前做一次缺字检查。
- 以最终版面宽度反推 SVG：正文标签建议不低于 9 pt，节点标题 10–11 pt，图内辅助文字不低于 8 pt；若缩到双栏宽度后低于此范围，应删减文字或拆图，而不是继续缩小。
- 主标题放在图外图注中；SVG 内仅保留短标题，避免在 Markdown 图注、SVG 内标题和 PNG 文件名重复三次并产生版本漂移。
- 路径标注使用反引号样式的等宽字体或清晰的短路径，例如 `engine/run_service.py`；过长路径移到图注的“Source”行。路径必须真实存在或明确标成接口/概念，不写臆测路径。
- 文件名建议用稳定的英文短名，例如 `architecture.svg`、`simulation-loop.svg`；中文解释放在 Markdown 标题/图注中。若同时保留 PNG，SVG 与 PNG 应来自同一源并在提交前做尺寸和内容核对。

### 4.5 颜色、灰度和打印

**来源明确要求/适用范围。** SVG 支持样式化和缩放；W3C 的可访问性规范关注名称、描述、角色和呈现，不为本项目规定调色板。颜色对比度的最终要求还取决于论文模板、打印流程和目标查看器。

**本仓库设计选择。**

- 颜色只做第二通道；类别还要靠边框、线型、位置、编号或文字区分。建议主结构以白底/浅灰填充、深灰文字和少量蓝色强调，避免红绿作为唯一对立编码。
- 采用“彩色屏幕 + 灰度打印”双检查：删除颜色后仍能区分模块边界、外部系统、控制流、数据来源和可选关系；重要线条不使用过浅灰。
- 字体与背景按 W3C WCAG 2.2 的文本对比度原则检查；普通文字目标至少 4.5:1，大号文字至少 3:1。该数值是通用可访问性基线，不是 OMG/C4 的图形配色规定。

来源：[W3C WCAG 2.2，1.4.3 Contrast (Minimum)](https://www.w3.org/TR/WCAG22/#contrast-minimum)（访问 2026-08-04）。

- SVG 输出不得依赖仅在深色背景有效的滤镜、透明叠加或渐变来表达语义。阴影可删除后仍应读懂；滤镜/透明度应在浏览器、Markdown 渲染器和导出 PDF 中各测试一次。

### 4.6 输出、可访问性和可复核性

**本仓库设计选择的最小验收清单：**

- SVG 有 `viewBox`，在目标论文宽度和放大查看时不裁剪箭头、文字或图例。
- 有 `<title>`、`<desc>`；`desc` 用一句到三句解释节点群、主路径和重要例外，不重复整幅图的所有可见文字。
- 所有可见节点的名称在纯文本提取或屏幕阅读测试中仍有意义；不要将整幅图导出为一张嵌入式位图后声称“有 SVG”。
- 关键语义不只靠颜色；用图例、编号、线型和文本复述。
- 路径标签与图注引用当前仓库真实文件；模块职责以代码和测试为准。
- SVG 与 PNG（若存在）尺寸、标题、节点数量和箭头方向一致；PNG 是兼容副本，不是第二个设计源。
- 论文提交的最终版另做一次 PDF/打印检查；本仓库不能仅凭 SVG 在浏览器中显示正常就宣称出版社验收通过。

## 5. 建议的三幅图及其边界

### 图 A：系统架构图（C4-inspired Container/Component）

**目的：** 让读者在一分钟内理解代码、仿真引擎、控制策略和产物的边界。

**推荐层次：**

```text
外部调用者：CLI / REST API / batch runner
  └─ 应用编排：RunService
       ├─ 场景与输入：SceneRegistry / VariantGenerator
       ├─ 控制：FixedTime / Actuated / CA-MP / CloudPolicy
       ├─ 运行时适配：SimulationRunner / TraCIBridge / MockBridge
       └─ 产物：RunArtifacts / metadata / metrics / tripinfo / summary
外部运行时：SUMO
```

**不应放入：** 20 个路口的全部 XML 文件、每个测试函数、每个算法内部公式、已经清理掉的历史结果目录。那些内容应放到对应的细节图或报告表格。

### 图 B：一次运行流程图（简化 BPMN/UML Activity）

**泳道：** Caller、`RunService`、Scene/Variant、SimulationRunner、Algorithm/CloudPolicy、TraCI/SUMO、Artifacts/Summary。

**最小编号：**

`F01` 接收并校验 `RunRequest` → `F02` 创建隔离 `RunArtifacts` → `F03` 取得 scene → `F04` 生成 `VariantBundle` → `F05` 构造算法/runner → `F06` 读取 `JointState` → `F07` 计算并校验动作 → `F08` 通过 TraCI 应用动作/推进 SUMO → `F09` 写 metrics/events/原始 XML → `F10` 从真实来源生成 `summary.json` → `F11` 返回 `RunResult`。

`F06`–`F08` 是循环，应使用一个明确的回边和 `steps`/停止条件；不要画成向下重复几十次的长图。异常分支应标明 `FAILED` metadata，而不是默认为“无输出”。

### 图 C：实验产物与证据链图

**目的：** 解释一次 run 与批量实验如何产生可追溯产物，不把文件存在性和历史验收状态混在一起。

**节点建议：** `RunRequest`、场景/流量变体、`run_id` 目录、`metadata.json`、`events.csv`、`metrics.csv`、`tripinfo.xml`、`summary.json`、`run_summaries.csv`/统计汇总。边标签写“生成”“读取”“汇总”“来源”。

**重要限制：** `output/README.md` 明确说明运行目录是可丢弃生成状态，历史 13-pass/360-run 产物已经清理；因此图中应写“artifact contract / generated at run time”，不能画成当前仓库必然存在的证据目录。若论文需要真实数据，应在图外引用实际保留的报告、manifest 或复核记录。

## 6. 发布前可执行检查表

### 结构与语义

- [ ] 图标题写明视角：C4-inspired architecture、UML Activity、BPMN-inspired flow 或 evidence lineage。
- [ ] 每个边界有责任含义；每条箭头有唯一语义；图例解释全部自定义编码。
- [ ] `RunService`、`SceneRegistry`、`VariantGenerator`、`SimulationRunner`、三种算法、`CloudPolicy`、`TraCIBridge`/`MockBridge`、SUMO 与产物没有被画成不真实的继承、部署或数据关系。
- [ ] 运行流程的循环、失败分支和产物来源可追溯；不是只画“输入 → 黑盒 → 结果”。

### 排版与打印

- [ ] 在论文实际版面宽度下，正文、图例、路径仍可读；没有用过密文字解决“所有内容必须同图”的冲动。
- [ ] 去色后仍可区分所有重要类别；低对比度虚线、透明填充和小字号已检查。
- [ ] 放大 SVG、Markdown 内嵌 SVG、导出 PNG/PDF 三种情况下，箭头端点、文字、边界和裁剪一致。
- [ ] SVG/PNG 文件名、图内短标题、Markdown 图注的版本信息一致，来源文件路径经过 `rg --files` 或代码阅读核实。

### 可访问性与来源

- [ ] 有 `<title>`、`<desc>` 和必要的 `aria-labelledby`；`desc` 能独立说明图的主路径。
- [ ] 文字保留为文本元素，或对轮廓化给出发布理由并保留可访问源文件。
- [ ] 图注写明来源模块/文件、是否省略细节、生成日期和适用的 commit/版本。
- [ ] 所有规范性结论链接到 OMG/W3C/C4 一手页面；本仓库的颜色、字号、布局、线型映射明确标为“设计选择”。

## 7. 来源清单（访问 2026-08-04）

| 来源 | 本文使用的范围 | 状态说明 |
| --- | --- | --- |
| [OMG UML 2.5.1](https://www.omg.org/spec/UML/2.5.1/) | UML 的官方定义、正式规范入口、不能随意自造 UML 语义 | 正式规范页面 |
| [OMG BPMN 2.0.2](https://www.omg.org/spec/BPMN/2.0.2/) | 流程图定位、利益相关者/软件流程精度、正式文件入口 | 正式规范页面 |
| [OMG ArchiMate 入口](https://www.omg.org/archimate/) | 仅用于识别其企业架构范围；未据此转述具体关系/颜色条款 | 使用前需复核具体版本 |
| [C4 Model](https://c4model.com/) | 抽象层级、层级图、notation/tooling 独立性 | 官方作者网站 |
| [C4 Diagrams](https://c4model.com/diagrams) | 静态结构图与 supporting diagrams、无需机械展开全部层级 | 官方作者网站 |
| [C4 Abstractions](https://c4model.com/abstractions) | system/container/component/code 的层级词汇 | 官方作者网站 |
| [W3C SVG 2](https://www.w3.org/TR/SVG2/) | SVG 的 XML、矢量/混合图形、缩放、独立/嵌入能力 | 页面标为 Candidate Recommendation；发布前按目标环境测试 |
| [W3C SVG 2 Text](https://www.w3.org/TR/SVG2/text.html) | SVG 文本输出与文本元素的规范入口 | 与目标查看器一起验证 |
| [W3C SVG 1.1 Title/Description](https://www.w3.org/TR/SVG11/struct.html#DescriptionAndTitleElements) | `<title>`、`<desc>` 的结构/描述用途 | W3C 规范页面 |
| [W3C SVG-AAM 1.0](https://www.w3.org/TR/svg-aam-1.0/) | SVG 到可访问性 API 的映射、名称/描述/角色/焦点方向 | 页面标为 Working Draft，且自带不应直接实现警告 |
| [W3C WAI-ARIA 1.2](https://www.w3.org/TR/wai-aria-1.2/) | `role`、名称与描述相关的通用可访问性背景 | W3C 规范页面 |
| [W3C WCAG 2.2 Contrast](https://www.w3.org/TR/WCAG22/#contrast-minimum) | 文本对比度作为无障碍检查的通用基线 | 不是 OMG/C4 的图形配色规定 |

## 8. 明确未声称的内容

- 本文没有把颜色、字号、箭头粗细、画布尺寸、图标或灰度策略归因于 OMG、C4 或 W3C；这些是本仓库的设计选择。
- 本文没有声称当前仓库已经生成、提交或通过出版社验收了新的 SVG；本文件只是研究与制图基线。
- 本文没有把 `MockBridge` 说成生产 SUMO；它在代码中是替代真实 TraCI 的测试实现。
- 本文没有把 `output/` 下历史矩阵目录说成当前存在；产物图仅描述运行时契约和来源关系。
- 本文没有继续检索或转述 IEEE/ACM 某个具体出版社模板；不同期刊对最终字号、线宽、颜色空间、图幅和文件格式的要求可能不同，投稿时应以目标期刊/会议的官方作者指南为准。
