# Architecture

## 模块职责

`docs/architecture/` 记录当前数据契约、模块接口和可引用的系统图示。它是运行时源码的说明，不包含可执行业务代码。

## 文件索引

| 路径 | 内容 |
| --- | --- |
| `interface.md` | 核心类型、算法引擎接口、API 和实验 CLI |
| `images/architecture.svg` | 统一运行容器架构与云端 / 边缘 / 终端映射 |
| `images/simulation-loop.svg` | 单步仿真控制循环与证据生成 |
| `images/team-org.svg` | 角色、模块与交付接口责任矩阵 |
| `images/dependencies.svg` | 模块依赖、只读输入与证据输出边界 |
| `images/timeline.svg` | 工程复现与交付阶段门控 |

## 发布方式

五张正式图以 `images/*.svg` 作为 Markdown、GitHub、论文 PDF 和打印的发布产物。它们由 Graphviz 的 `dot` 布局结果整理而来，并保留 `title`、`desc`、`role="img"`、`aria-labelledby` 和边标签白底，避免箭头穿过文字。本仓库只保留 SVG 发布物，不提交临时 DOT 源或 PNG 兼容副本。

Markdown 应直接引用 `images/` 下的 SVG。若需要重新设计图示，应在仓库外生成临时 DOT，并在导出和检查完成后只将最终 SVG 放回该目录。

## 依赖与限制

- 图示是静态设计资料，不参与 Python、Docker 或测试运行。
- `data/intersection_data/` 在图中保持只读，运行产生的证据按 `run_id` 隔离。
- 修改图示后，应重新检查 SVG 的 XML、无障碍元数据、边标签、窄屏渲染和现有 Markdown 链接。
- 具体运行行为仍以源码、测试和实际 SUMO 结果为准，图示不替代实验验证。
