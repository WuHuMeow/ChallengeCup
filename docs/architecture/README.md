# Architecture

## 模块职责

`docs/architecture/` 记录当前数据契约、模块接口和可引用的系统图示。它是运行时源码的说明，不包含可执行代码。

## 文件索引

| 路径 | 内容 |
| --- | --- |
| `interface.md` | 核心类型、算法/引擎接口、API 和实验 CLI |
| `images/architecture.svg`、`architecture.png` | 系统整体架构图 |
| `images/simulation-loop.svg`、`simulation-loop.png` | 仿真循环与 ML 路径 |
| `images/team-org.svg`、`team-org.png` | 团队组织图 |
| `images/dependencies.svg` | 模块依赖图 |
| `images/timeline.svg`、`timeline.png` | 开发阶段时间线 |

## 使用方式

在 Markdown 中从文档所在目录使用相对链接引用 `images/` 下资源；SVG 是首选格式，PNG 用于不支持 SVG 的查看器。`images/` 是项目架构图的唯一规范目录。

## 依赖与限制

- 图示是静态设计资料，不参与 Python、Docker 或测试运行。
- 修改图示后应同时更新 SVG/PNG 版本（若两种格式都存在）并复核现行文档链接。
- `interface.md` 描述当前契约和历史演进，具体行为仍以源码和测试为准。
