# API

## 模块职责

`api/` 使用 FastAPI 暴露健康检查、场景查询、运行状态和车路云协同接口，供 Swagger、Postman 或演示前端调用。

## 文件索引

| 文件 | 作用 |
| --- | --- |
| `server.py` | FastAPI 应用、请求模型和全部路由 |

## 命令与接口

```powershell
uvicorn api.server:app --reload
```

| 路由 | 当前行为 |
| --- | --- |
| `GET /health` | 返回服务健康状态 |
| `GET /scenes` | 通过 `SceneRegistry` 返回可发现路口 |
| `POST /run` | 生成运行 ID 并记录内存状态，不启动 SUMO |
| `GET /status` | 返回内存中的最近运行状态 |
| `/api/scenes`、`/api/simulation/*` | 接口占位或静态响应 |
| `/api/cloud/predict`、`/api/edge/control`、`/api/vehicle/status` | 协同接口占位响应 |

## 输入与输出

- `StartRequest` 输入 `intersection_id`、`algorithm` 和 `steps`。
- `SwitchRequest` 输入算法名称。
- 输出为 JSON；交互式 OpenAPI 文档位于 `/docs`。

## 依赖

- 依赖 FastAPI、Pydantic 和 Uvicorn。
- `/scenes` 依赖 `scenes.SceneRegistry` 与本地路口数据。
- 请求/响应数据契约与核心类型定义见 `docs/architecture/interface.md`。

## 已知限制

- `/run` 和 `/api/simulation/*` 不会创建后台任务或启动 `SimulationRunner`。
- 多数 `/api/*` 路由尚未接入 `CloudPolicy`、控制算法或实时指标。
- 运行状态仅保存在当前 Python 进程内，不支持并发隔离、持久化或跨进程查询。
- `/scenes` 捕获所有异常并返回空列表，调用方无法从响应区分空数据与配置错误。
