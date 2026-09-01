# 评委视角 Web 控制台设计

> 日期：2026-08-23  
> 适用分支：`codex/judge-final-release`  
> 设计依据：项目赛题 PDF、当前 FastAPI 契约、Task 16 验证结果和现有发布计划

## 1. 目标与依据

本设计把项目现有仿真与证据链包装为一个评委可直接操作的 Web 控制台。设计优先满足赛题 PDF 的四类可核验要求：

1. 使用真实雄安路口场景构建或导入仿真环境，并支持扰动注入。
2. 展示可运行的协同管控算法和清晰的输入/输出接口。
3. 用基线对比、指标图表、时空帧和安全指标展示实验结果。
4. 提供从场景进入、算法运行、实时协同到结果解释的完整演示路径。

PDF 第 2、4、7-12 页强调真实场景、20 个路口工程文件、算法代码、基线对比、指标可视化和 5-8 分钟完整演示。当前仓库已具备 20 个场景、SUMO/TraCI 运行链路、FastAPI 评委 API、运行级证据封存和 PNG 帧发布；当前缺口是 `web/` 控制台、浏览器验证和一键演示入口。设计不会把尚未取得真实证据的 Docker 或第二环境状态显示为通过。

## 2. 方案选择

### 2.1 方案 A：React/Vite 构建后由 FastAPI 托管（选定）

`web/` 使用 React 18、TypeScript 5、Vite、Recharts、Lucide 和 Playwright。生产构建输出到 `api/static/dist`，由现有 `api/static.py` 进行 containment-safe 静态托管；开发时 Vite 仅代理 `/api` 到 FastAPI。前端不依赖外部 CDN。

选择理由：评委只需启动一个 FastAPI 服务即可完成演示，和 Task 16 已冻结的 `/api/*`、WebSocket、PNG frame 契约直接相接；构建产物可随发行包复现，符合 PDF 对可运行系统和工程化部署的要求。

### 2.2 未选方案

- 独立前后端生产服务会引入第二个端口、跨源 WebSocket 和额外启动步骤，不利于 PDF 要求的完整演示和后续一键启动。
- Jinja/HTMX 可减少 Node 依赖，但会分散实时状态、图表和帧序列逻辑，无法自然承载既定的 typed client、Recharts 和 Playwright 验证。

## 3. 架构与数据流

前端分为四层：

- `api/client.ts`：唯一 HTTP/WebSocket 适配层，定义响应类型和错误归一化。
- `state/runStore.ts`：保存选择项、当前运行、指标、事件、帧序列和错误，不保存文件系统路径。
- 视图组件：Simulation、Comparison、History、Scene 只消费 typed client 和 store。
- `styles.css`：响应式布局、稳定的帧画布尺寸、可访问焦点态和状态颜色。

实时流程如下：

```text
场景/算法/负载选择
  -> POST /api/runs
  -> 保存 run_id 并连接 /api/runs/{run_id}/events
  -> 有界轮询 /api/runs/{run_id}/frame?sequence=n
  -> 接收 metrics/action/safety/status/terminal 事件
  -> 展示实时帧、仿真时间、指标和安全状态
  -> stop 或 terminal 后读取 /api/results/{run_id}
```

帧请求只接受 `X-Frame-Sequence` 大于当前 store 序列的响应；响应过期、run_id 不匹配或 sequence 回退时丢弃。WebSocket 断线不伪造完成状态，显示可重连的断线状态并保留最后一帧。

## 4. 视图和交互边界

### Simulation

提供真实场景、算法、流量倍率、随机种子和扰动选择；展示运行状态、PNG SUMO 帧、帧序列、仿真时间、当前相位、指标卡、安全计数和原生 SUMO-GUI 按钮。快速演示固定走一条代表性短时路径，并明确标注“快速演示”；只有 `/api/results` 返回的已封存结果标记为“正式证据”。

### Comparison

从已验证结果中选择算法和场景，按统一指标展示基线与 CA-MP 的对比。组件不重新计算或修改正式数据，不把缺失精确量的 `null` 渲染成 0。

### History

读取 `/api/results`，显示 run_id、算法、状态和摘要；隐藏 `run_dir` 等内部路径。点击结果前先确认服务端证据已封存，无法验证的运行显示为不可用而不是历史成绩。

### Scene

展示 `/api/scenes` 的真实清单、来源文件摘要、SHA-256、步长、TLS/lane 数量、验证状态和警告，帮助评委确认当前选择对应真实路口场景。

## 5. 错误、安全和可访问性

- 统一处理 loading、空数据、未知 run_id、404 frame、运行失败、WebSocket 断线、native GUI 不支持和服务不可达。
- 不在前端拼接或暴露服务端文件路径；结果详情依赖后端 output-root containment 和封存校验。
- 使用 Lucide 图标和可读标签，所有图标按钮有 aria-label；键盘可访问，桌面和窄屏布局均保持固定帧区域，避免内容抖动或文字遮挡。
- 快速演示和正式证据使用不同的视觉标签，禁止用演示结果替换正式实验结果。

## 6. 测试与验收

实现前先为 typed client、sequence 门禁、事件断线和证据标签写 RED 测试，再实现 GREEN。最终门禁包括：

1. `npm ci`、TypeScript typecheck 和 Vite build 成功，构建产物存在于 `api/static/dist`。
2. Playwright fixture 覆盖四个视图、启动/停止、断线、错误状态、真实 PNG 非空和旧帧丢弃。
3. FastAPI 现有全量测试、OpenAPI/Postman 逐字节契约测试继续通过。
4. `git diff --check`、静态检查和受保护文件哈希/跟踪清单保持不变。

## 7. 非目标和后续依赖

- 本 Task 不修改算法核心、SUMO 原始工程、`赛题资料.7z` 或 `data/intersection_data`。
- Docker live、第二环境复现、正式 540 次矩阵和最终发行包由 Task 18-24 继续完成；控制台只能展示已有可验证证据。
- PyQt 原生看板不进入必交路径；原生 SUMO-GUI 仅通过现有 API 控件触发。
