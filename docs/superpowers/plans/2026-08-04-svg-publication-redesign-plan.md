# ChallengeCup 论文式系统流程图 SVG 重设计实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (\`- [ ]\`) syntax for tracking.

**Goal:** 将 Markdown 使用的 5 张架构类 SVG 统一重绘为论文式、系统化且与当前仓库和赛题 PDF 一致的可追溯图表，并同步活跃文档说明后提交到 WuHuMeow/ChallengeCup 的 GitHub 远端。

**Architecture:** 入口统一汇入 RunService，经过 SceneRegistry/VariantGenerator/SimulationRunner，由 CloudPolicy、三种算法和 EdgeChannel 完成决策，再通过 TraCIBridge/MockBridge 与 SUMO 或 Mock 交互，最后写入按 run_id 隔离的证据产物。五张图共享同一套无渐变论文图表规范，但分别承担架构、单步流程、依赖、角色责任和复现交付阶段五个叙事任务。

**Tech Stack:** 手工 SVG XML、Markdown、PowerShell、rg、XML 解析、浏览器渲染检查、现有 Python 编译/契约检查、Git。

## Global Constraints

- data/intersection_data/ 只读；不得修改原始 SUMO 场景。
- 不虚构 CloudCoordinator、EdgeNode、网络化多机服务、已完成的大型矩阵或已提交的 Word/PPT/视频。
- 算法名固定为 fixed_time、actuated、ca_maxpressure；CA-MP 必须体现合法相位、容量归一化、下游溢出门控、CloudPolicy 预测和安全过渡。
- 20 × 3 × 2 × 3 = 360 只表示实验设计规模，不表示当前证据已完成。
- 实线表示运行时调用/控制，开放箭头表示读取/返回，虚线表示可选/周期性/延迟，点线或点划线表示来源/离线验证/交付证据；每张图画图例。
- SVG 必须有 viewBox、role、aria-labelledby、title、desc、唯一 id/marker 和可检索 text；不使用外部图片、渐变、阴影、emoji。
- 活跃 Markdown 保留 SVG 文件名和相对链接；历史计划不改写。
- 所有验证命令从 C:\Users\peng\Desktop\workplace\main\project 执行。

---

### Task 1: 固定一手研究基线与 SVG 视觉令牌

**Files:**
- Verify: docs/notes/svg-publication-style-research.md
- Create: docs/superpowers/specs/2026-08-04-svg-publication-redesign-design.md
- Create: docs/superpowers/plans/2026-08-04-svg-publication-redesign-plan.md

**Interfaces:**
- Consumes: OMG UML/BPMN、C4 Model、W3C SVG/WAI-ARIA/WCAG 官方资料和仓库真实模块。
- Produces: 已区分“规范来源明确要求”和“本仓库设计选择”的研究/设计/实施基线。

- [ ] **Step 1: Verify the research note**

Run:

~~~powershell
Get-Content -LiteralPath docs/notes/svg-publication-style-research.md -Encoding UTF8 -Raw
rg -n "https?://|规范要求|设计选择|访问 2026-08-04" docs/notes/svg-publication-style-research.md
~~~

Expected: 研究笔记存在；关键结论包含一手来源 URL 和访问日期；没有要求修改源码或原始数据。

- [ ] **Step 2: Self-review the design and plan**

Read the specification and this plan from top to bottom. Confirm every task names its exact files, inputs, outputs, commands and expected result; confirm the five diagram topics, active Markdown updates, rendering checks and GitHub delivery all have a corresponding task. Resolve any ambiguity before editing formal SVGs.

### Task 2: 统一 SVG 框架并重绘 architecture.svg

**Files:**
- Modify: docs/architecture/images/architecture.svg

**Interfaces:**
- Consumes: docs/interface.md、docs/architecture/interface.md、api/server.py、engine/run_service.py、engine/runner.py、cloud/cloud_policy.py、engine/edge_channel.py、engine/traci_bridge.py。
- Produces: C4-inspired 容器/组件图，展示入口、统一运行核心、Cloud/Edge/End 映射、SUMO/Mock 适配和 run_id 证据产物。

- [ ] **Step 1: Add the publication SVG metadata and base frame**

Use a white background, stable viewBox, deep-gray text, dark-blue structure, limited teal/orange accents, and these root attributes:

~~~xml
<svg xmlns="http://www.w3.org/2000/svg"
     viewBox="0 0 1440 820"
     role="img"
     aria-labelledby="architecture-title architecture-desc">
  <title id="architecture-title">统一运行容器架构与 Cloud Edge End 映射</title>
  <desc id="architecture-desc">CLI、REST API 和 PDF 矩阵入口统一进入 RunService，经过场景变体与仿真运行器，由 CloudPolicy、控制算法和桥接层驱动 SUMO 或 Mock，并生成按 run_id 隔离的实验证据。</desc>
</svg>
~~~

Add semantic group ids: inputs, run-service-boundary, cloud-edge-end-mapping, simulation-and-bridges, evidence-outputs, legend. All visible labels remain text nodes.

- [ ] **Step 2: Draw the actual repository containers**

Draw, in left-to-right order:

~~~text
experiments.runner / api.server / scripts.run_pdf_matrix
-> RunRequest -> RunService(max_workers=1)
-> SceneRegistry -> VariantGenerator -> SimulationRunner
-> TraCIBridge or MockBridge <-> SUMO
-> RunArtifacts / run_id / metrics.csv / tripinfo.xml / summary.json / run_metadata.json
~~~

Inside the control band, show fixed_time, actuated and ca_maxpressure. Show CloudPolicy as CA-MP prediction/parameter input. Label EdgeChannel as optional delay/filter. Do not draw CloudCoordinator, EdgeNode, model.pkl or member numbers.

- [ ] **Step 3: Add Cloud/Edge/End mapping and legend**

Show Cloud = CloudPolicy; Edge = EdgeChannel plus algorithms and ControlAction; End = TraCIBridge/MockBridge plus SUMO and JointState. Use real labels RunRequest, JointState, ControlAction and ActionResult on connectors. Add a line legend for synchronous runtime, returned state, optional/periodic channel and evidence source.

- [ ] **Step 4: Verify the architecture facts**

Run:

~~~powershell
rg -n "CloudCoordinator|EdgeNode|3600 步|model\.pkl|成员[0-9]" docs/architecture/images/architecture.svg
rg -n "RunService|SceneRegistry|VariantGenerator|SimulationRunner|CloudPolicy|EdgeChannel|TraCIBridge|MockBridge|SUMO|summary\.json|run_metadata\.json" docs/architecture/images/architecture.svg
~~~

Expected: first command no output; second command finds every required real component or path.

### Task 3: 重绘 simulation-loop.svg

**Files:**
- Modify: docs/architecture/images/simulation-loop.svg

**Interfaces:**
- Consumes: engine/runner.py 的 _tick() 和终态逻辑、algorithms/ca_max_pressure.py、engine/action_validation.py、experiments/summary.py。
- Produces: 带泳道/编号/回边的单次运行流程和 CA-MP 决策子图。

- [ ] **Step 1: Draw the numbered execution flow**

Use F01-F11 with this order:

~~~text
F01 RunRequest 校验
F02 VariantBundle 与隔离 RunArtifacts
F03 TraCIBridge 或 MockBridge 启动
F04 get_state() -> JointState
F05 可选 EdgeChannel send/receive
F06 CloudPolicy predict/dispatch_params
F07 algorithm.step() -> ControlAction[]
F08 action validation + apply_actions() -> ActionResult[]
F09 simulationStep()
F10 metrics/events/step log
F11 tripinfo.xml + metrics.csv -> summary.json + run_metadata.json
~~~

Draw configured_end, exhausted, stopped, disconnected and failed as explicit terminal branches. Draw a single labeled back edge next simulation step from F10 to F04. Do not write a fixed 3600-step loop.

- [ ] **Step 2: Draw the CA-MP subgraph**

Number A01-A07 for normalized upstream/downstream queue pressure, predicted arrivals, downstream overflow gate, legal green phase, minimum/maximum green guard, yellow/all-red transition and dynamic duration with set_phase(int) plus set_phase_duration(float). Mark CloudPolicy as an in-process policy source, not an independent network server.

- [ ] **Step 3: Verify flow semantics**

Run:

~~~powershell
rg -n "3600|CloudCoordinator|EdgeNode|force release|incoming-lane occupancy" docs/architecture/images/simulation-loop.svg
rg -n "JointState|EdgeChannel|CloudPolicy|ControlAction|ActionResult|configured_end|summary\.json|run_metadata\.json|next simulation step" docs/architecture/images/simulation-loop.svg
~~~

Expected: first command no output; second command finds all required loop terms and the explicit feedback label.

### Task 4: 重绘 dependencies.svg

**Files:**
- Modify: docs/architecture/images/dependencies.svg

**Interfaces:**
- Consumes: Python imports and docs/architecture/interface.md 的数据层/部署边界。
- Produces: 五层依赖 DAG，区分代码依赖、运行时输入/输出和可选 ML 扩展。

- [ ] **Step 1: Draw the actual dependency layers**

Use these exact headings:

~~~text
Input: data/intersection_data/ (read-only), config/default.yaml, SUMO
Contracts: core.types, core.run_models, core.config
Execution: scenes, engine, algorithms, cloud, ml (optional)
Entrypoints: experiments, api, scripts
Evidence: metrics.csv, tripinfo.xml, summary.json, visualization, offline manifest
~~~

Use solid arrows for Python dependencies and dashed arrows for runtime file flow. Mark data/intersection_data/ read-only and output run_id directories independently writable.

- [ ] **Step 2: Remove the inaccurate serial chain**

Run:

~~~powershell
rg -n "CSV.*ML|model\.pkl|成员[0-9]|仿真.*算法.*实验.*报告" docs/architecture/images/dependencies.svg
rg -n "read-only|只读|optional|可选|data/intersection_data|core\.types|core\.run_models|engine|algorithms|cloud|experiments|api|summary\.json|tripinfo\.xml" docs/architecture/images/dependencies.svg
~~~

Expected: first command no output; second finds the five layers and boundary terms.

### Task 5: 重绘 team-org.svg

**Files:**
- Modify: docs/architecture/images/team-org.svg

**Interfaces:**
- Consumes: docs/tasks/current-status.md、任务角色文件、core/engine/algorithms/experiments/report 目录。
- Produces: 8-role responsibility matrix and code/document/external-evidence boundaries.

- [ ] **Step 1: Draw three responsibility groups**

Use:

~~~text
契约与仿真: TL -> core/contract/integration; IA -> scenes/data/SUMO; IB -> engine/api/docker/docs
算法与实验: AA -> FixedTime/Actuated; AB -> CA-MP/CloudPolicy; EX -> experiments/visualization/matrix
交付与表达: DA -> report/Word/PPT; DB -> charts/video/demo materials
~~~

Use role boxes with actual repository paths and arrows for contract -> algorithm -> matrix -> report alignment. The graph is a responsibility interface, not an assertion of final deliverable completion.

- [ ] **Step 2: Add honest status language**

Show 代码/本地验证 for evidenced implementation and 待外部核验 for Docker live, second-machine reproduction, Word/PDF report, PPT, video and submission package. Do not show meeting times, member numbers or unverified completion checkmarks.

### Task 6: 重绘 timeline.svg

**Files:**
- Modify: docs/architecture/images/timeline.svg

**Interfaces:**
- Consumes: docs/deployment.md、docs/tasks/current-status.md、docs/ia-ib-final-verification.md、scripts/run_pdf_matrix.py 和 PDF 提交要求。
- Produces: 当前工程复现/交付阶段门控图。

- [ ] **Step 1: Draw the lifecycle with current states**

Use:

~~~text
赛题约束与只读场景 [代码/文档]
-> 契约与统一入口 [代码/本地验证]
-> 本地 SUMO/Mock 与算法验证 [代码/本地证据]
-> 20×3×2×3 矩阵与图表重生成 [需重生成]
-> Docker live / 第二机器复现 [not_run]
-> 报告 / PPT / 视频 / 提交包 [未发现或待交付]
~~~

Show the 360 value as experiment design only. Add a gate legend stating not_run is not pass. Remove 7/20-8/31 historical dates, meeting schedules and “360 completed” wording.

- [ ] **Step 2: Verify the stage wording**

Run:

~~~powershell
rg -n "7/20|7/27|8/3|8/10|8/17|8/24|会议|接口冻结|3600|已完成.*360" docs/architecture/images/timeline.svg
rg -n "not_run|需重生成|待外部核验|20.*3.*2.*3|Docker|第二机器|报告|PPT|视频" docs/architecture/images/timeline.svg
~~~

Expected: first command no output; second finds current stages and status terms.

### Task 7: 同步活跃 Markdown 图表说明

**Files:**
- Modify: docs/architecture/README.md
- Modify: docs/guides/markdown-guide.md
- Modify: docs/总路线.md
- Modify: docs/tasks/roadmap.md

**Interfaces:**
- Consumes: final SVG titles/descriptions and relative paths.
- Produces: accurate descriptions, topic-specific alt text and no false PNG claims.

- [ ] **Step 1: Update the asset tables**

Run:

~~~powershell
rg -n "architecture\.svg|simulation-loop\.svg|team-org\.svg|dependencies\.svg|timeline\.svg|\.png" docs/architecture/README.md docs/guides/markdown-guide.md
~~~

Expected: all five SVGs point to docs/architecture/images/ and descriptions match their new topics. If a PNG is not present, documentation does not call it an existing backup.

- [ ] **Step 2: Update active alt text and verify links**

Run:

~~~powershell
rg -n "!\[.*\]\(.*(architecture|simulation-loop|team-org|dependencies|timeline)\.svg\)" --glob '*.md' .
rg --files docs/architecture/images | rg "(architecture|simulation-loop|team-org|dependencies|timeline)\.svg$"
~~~

Expected: every active reference has topic-specific alt text and each referenced file exists.

### Task 8: Validate SVG structure, render, and diff scope

**Files:**
- Test: all five docs/architecture/images/*.svg and active Markdown references

**Interfaces:**
- Consumes: final SVG XML and Markdown.
- Produces: fresh structural, visual and link evidence.

- [ ] **Step 1: Parse every SVG**

Run:

~~~powershell
$files = Get-ChildItem -LiteralPath docs/architecture/images -Filter '*.svg'
if($files.Count -ne 5){ throw "Expected 5 SVGs, found $($files.Count)" }
foreach($file in $files){
  [xml]$xml = Get-Content -LiteralPath $file.FullName -Encoding UTF8 -Raw
  $svg = $xml.DocumentElement
  if($svg.LocalName -ne 'svg'){ throw "$($file.Name) is not an SVG root" }
  if(-not $svg.viewBox){ throw "$($file.Name) has no viewBox" }
  if(-not $svg.title){ throw "$($file.Name) has no title" }
  if(-not $svg.desc){ throw "$($file.Name) has no desc" }
  if(-not $svg.role){ throw "$($file.Name) has no role" }
  Write-Output "$($file.Name): $($file.Length) bytes; viewBox=$($svg.viewBox)"
}
~~~

Expected: 5/5 parse, with title, description, role and viewBox.

- [ ] **Step 2: Check content hygiene and duplicate ids**

Run:

~~~powershell
rg -n "linearGradient|feDropShadow|<image|emoji|CloudCoordinator|EdgeNode|3600 步|model\.pkl|成员[0-9]" docs/architecture/images/*.svg
Get-ChildItem docs/architecture/images/*.svg | ForEach-Object {
  $ids = [regex]::Matches((Get-Content -LiteralPath $_.FullName -Encoding UTF8 -Raw), 'id="([^"]+)"') | ForEach-Object { $_.Groups[1].Value }
  if(($ids | Sort-Object -Unique).Count -ne $ids.Count){ throw "$($_.Name) has duplicate SVG ids" }
}
~~~

Expected: no forbidden terms/visual artifacts and no duplicate ids.

- [ ] **Step 3: Render at wide and narrow widths**

Open each absolute SVG path in a browser and inspect at a wide viewport and a narrow viewport. Confirm title, legend, long paths, Chinese labels, connectors and status chips stay inside the viewBox without overlap. Save screenshots outside the repository only.

- [ ] **Step 4: Run focused repository checks**

Run:

~~~powershell
python -m compileall core algorithms engine cloud api experiments ml visualization scripts -q
git diff --check
git status --short
git diff --stat
~~~

Expected: compileall and diff check exit 0; status contains only planned documentation, SVG and research/spec/plan files.

### Task 9: Commit and deliver to GitHub without overwriting Gitee origin

**Files:**
- Modify: local .git/config only if needed to add a github remote
- Commit: all files listed by the final diff review

**Interfaces:**
- Consumes: fresh verification evidence and clean scope.
- Produces: one Git commit and a verified branch ref at https://github.com/WuHuMeow/ChallengeCup.git.

- [ ] **Step 1: Recheck branch and remotes**

Run:

~~~powershell
git branch --show-current
git remote -v
git status --short --branch
~~~

Expected: current branch and existing Gitee origin are recorded; origin is not silently replaced.

- [ ] **Step 2: Add or verify a separate GitHub remote**

Run:

~~~powershell
if(-not (git remote | Select-String '^github$')){
  git remote add github https://github.com/WuHuMeow/ChallengeCup.git
}
if((git remote get-url github) -ne 'https://github.com/WuHuMeow/ChallengeCup.git'){
  throw 'github remote URL is not the requested repository'
}
git remote -v
~~~

Expected: github resolves exactly to the user-requested GitHub repository while origin remains unchanged.

- [ ] **Step 3: Stage, commit and verify before pushing**

Run:

~~~powershell
git add docs/architecture/images/architecture.svg docs/architecture/images/simulation-loop.svg docs/architecture/images/dependencies.svg docs/architecture/images/team-org.svg docs/architecture/images/timeline.svg docs/architecture/README.md docs/guides/markdown-guide.md docs/总路线.md docs/tasks/roadmap.md docs/notes/svg-publication-style-research.md docs/superpowers/specs/2026-08-04-svg-publication-redesign-design.md docs/superpowers/plans/2026-08-04-svg-publication-redesign-plan.md
git diff --cached --check
git commit -m "docs: redesign architecture flowcharts as publication figures"
git status --short --branch
~~~

Expected: staged diff check exits 0; commit succeeds; no unrelated files are staged and the worktree is clean except any intentional remote config.

- [ ] **Step 4: Push the current branch and verify exact remote ref**

Run:

~~~powershell
git push -u github HEAD
$branch = git branch --show-current
$local = git rev-parse HEAD
$remote = (git ls-remote --heads github $branch).Split([char]9)[0]
if($remote -ne $local){ throw "Remote $branch does not point to $local; got $remote" }
Write-Output "github/$branch -> $remote"
~~~

Expected: push exits 0 and the GitHub branch points to the same commit. Report the exact branch/ref; do not claim merge to GitHub main unless a PR or merge is separately verified.
