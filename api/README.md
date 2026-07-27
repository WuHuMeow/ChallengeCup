# API

## 模块职责

`api/` 使用 FastAPI 暴露健康检查、场景查询、异步仿真运行和车路云协同接口，供 Swagger、Postman 或演示前端调用。

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
| `GET /api/health` | 返回 `status` 和单工作线程数 |
| `GET /api/scenes` | 通过 `SceneRegistry` 返回可发现路口 |
| `POST /api/runs` | 校验请求、创建运行目录并由 `RunService` 异步提交 SUMO 运行 |
| `GET /api/runs/{run_id}` | 返回已提交运行的状态、原因、目录和可用摘要 |
| `GET /api/runs/{run_id}/metrics` | 返回已完成运行的 `summary` 指标；不可用时为 404 |
| `POST /api/runs/{run_id}/stop` | 请求停止已知运行；不可停止时为 409 |
| `POST /api/cloud/predict` | 对 `JointState` 调用 `CloudPolicy.predict()` |
| `POST /api/edge/control` | 对 `JointState` 调用 `CAMaxPressureAlgorithm.step()` |

`/health`、`/scenes`、`/run`、`/status` 和 `/api/simulation/*` 是已标记 deprecated 的兼容路由；新调用方应使用
`/api/*` 契约。

## 输入与输出

- `POST /api/runs` 接收 `intersection_id`、`algorithm`、`steps`、`flow_multiplier`、`seed`、可选边缘延迟/方向、
  场景变体和 CA-MP 参数；请求模型见 `api/models.py`。
- 运行结果为 JSON，包含 `run_id`、生命周期状态、`run_dir` 和可用的 `summary`；运行文件由服务在
  `output/runs/`（或服务配置的根目录）运行时创建。
- 交互式 OpenAPI 文档位于 `/docs`；可用 `python scripts/export_api_contract.py` 刷新 `docs/api/` 中的契约文件。

## 依赖

- 依赖 FastAPI、Pydantic 和 Uvicorn。
- 路由依赖 `scenes.SceneRegistry`、`engine.RunService`、`CloudPolicy` 和 CA-MP 算法；真实运行还需要 SUMO/TraCI 和本地路口数据。
- 请求/响应数据契约与核心类型定义见 `api/models.py`、`core.run_models` 和 `docs/interface.md`。

## 已知限制

- 运行队列固定为一个工作线程，以保护全局 TraCI 客户端；状态仅保存在当前 Python 进程内，不支持重启后的查询或跨进程协调。
- `/api/runs` 会启动真实运行，不是模拟占位接口；API 进程必须具备 SUMO/TraCI、数据和可写输出目录。
- `/api/cloud/predict` 和 `/api/edge/control` 是同步计算接口，不会写入运行目录，也不提供网络化云端服务。
