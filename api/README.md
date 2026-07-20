# api/

## 模块职责

REST API 层，基于 FastAPI 提供实验控制、场景管理、算法切换、指标查询等接口，同时暴露云-边-端协同端点。

## 当前完成情况

- [x] `server.py`：FastAPI 应用骨架，已定义全部端点（mock 实现）。
- [ ] 所有端点目前返回 mock 数据，未接入真实 registry/runner。

## 待完成情况

- [ ] 接入 `scenes.registry.SceneRegistry`，实现 `/api/scenes` 真实数据。
- [ ] 接入 `engine.runner.SimulationRunner`，实现 `/api/simulation/start|stop`。
- [ ] 接入 `experiments.runner.run_batch`，实现 `/api/experiments/run`。
- [ ] 接入 `cloud.cloud_policy.CloudPolicy`，实现 `/api/cloud/predict`。
- [ ] 接入 `algorithms.ml_enhanced.MLEnhancedAlgorithm`，实现 `/api/edge/control`。
- [ ] 编写 `docs/api-spec.md` 接口文档与 Postman Collection。
- [ ] 绘制 `docs/数据流图.png`。

## 需求分析

| 需求 | 说明 |
|------|------|
| 实验控制 | 启动/停止仿真、切换算法、启动跑批 |
| 场景管理 | 列出场景、加载场景 |
| 结果查询 | 当前指标、对比结果 |
| 云-边-端接口 | `/api/cloud/*`、`/api/edge/*`、`/api/vehicle/*` 体现三层协同 |
| 接口文档 | Postman Collection + Swagger UI |

## 关键文件

| 文件 | 说明 |
|------|------|
| `server.py` | FastAPI 应用 |

## 对外接口

```bash
uvicorn api.server:app --reload
# 访问 http://127.0.0.1:8000/docs
```

## 负责人

- 成员6（后端负责）主责，成员7（前端负责）对接数据格式。
