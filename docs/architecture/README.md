# Architecture

## 模块职责

`docs/architecture/` 记录当前数据契约、模块接口和可引用的系统图示。它是运行时源码的说明，不包含可执行代码。

## 文件索引

| 路径 | 内容 |
| --- | --- |
| `interface.md` | 核心类型、算法/引擎接口、API 和实验 CLI |
| `images/architecture.svg` | 统一运行容器架构与 Cloud/Edge/End 映射 |
| `images/simulation-loop.svg` | 单次仿真控制循环与证据生成 |
| `images/team-org.svg` | 角色、模块与交付接口责任矩阵 |
| `images/dependencies.svg` | 模块依赖、只读输入与证据输出边界 |
| `images/timeline.svg` | 工程复现与交付阶段门控 |

## 使用方式

在 Markdown 中从文档所在目录使用相对链接引用 `images/` 下资源。本次五张图以 SVG 作为规范发布源，图内保留 `title`、`desc` 和可检索文本，便于 GitHub、论文排版和无障碍阅读。`images/` 是项目架构图的唯一规范目录。

目录中若保留 PNG，它们只能视为历史兼容导出；新增文档应引用 SVG，不能把未从本次 SVG 重新导出的 PNG 当作同步版本。

## 依赖与限制

- 图示是静态设计资料，不参与 Python、Docker 或测试运行。
- 修改图示后应先完成 SVG 的 XML、文本和渲染检查，并复核现行文档链接；若需要发布 PNG，必须从同一 SVG 重新导出并核对内容。
- `interface.md` 描述当前契约和历史演进，具体行为仍以源码和测试为准。
