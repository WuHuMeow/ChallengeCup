# Interface Closure Design Spec

> 工程整改规范：以 README 为唯一设计依据，逐文件审计目录职责，补齐基础框架代码，保证模块间调用闭环。
> 不实现复杂算法，只保证接口闭环。

- 日期：2026-07-21
- 状态：已批准
- 验收模式：静态闭环 + 动态闭环

---

## §1 范围与原则

### 目标

构建一个结构完整、接口统一、可持续开发的工程框架。

### 范围

README 项目结构中列出的全部模块：core / engine / scenes / algorithms / cloud / ml / experiments / visualization / api / examples / tests / config / docker。

### 原则

1. **README 是唯一设计依据**；发现 README 与实际代码冲突时，先报告再建议，不擅自改架构。
2. **最小可运行实现（MVI）**——每个模块能 import、能调用、有合理返回值。
3. **核心算法只留扩展点**——CA-MP 三项创新、EWMA 训练仅保留 TODO，不实现最终逻辑。
4. **接口面向最终形态**——后续替换内部逻辑时，其他模块零修改。
5. **不写临时代码**——不为 Demo 编写影响后续正式实现的临时逻辑。
6. **向后兼容**——不随意修改公共接口、目录结构和文件命名；若必须调整，先说明原因、影响范围及迁移方案。
7. **逐模块验证**——每完成一个模块，先完成静态检查与基础运行验证，再进入下一模块。

### 验收标准

- `python -m pytest tests/ -v` 全部通过
- `python examples/run_demo.py 1 ca_maxpressure` 全流程无异常，完整调用链走通
- `uvicorn api.server:app` 启动成功，`/docs`、`/health`、`/scenes`、`/run`、`/status` 可访问
- README 每个模块路径对应实际可运行代码
- 不存在 P0、P1 遗留问题

### 动态闭环调用链

```
config.load() → registry.get_scene(1) → Engine(mock) → CAMaxPressure.step()
    → CloudCoordinator.predict() → Collector.snapshot() → Metrics.compute() → print/输出
```

每一步必须有实际函数调用（非跳过），即使内部使用 mock 数据。

---

## §2 第一阶段：静态审计

### 方法

按 README 项目结构树逐文件检查，产出审计表。

### 检查维度

| # | 维度 | 检查内容 |
|---|------|----------|
| 1 | 存在性 | README 列出的文件是否存在 |
| 2 | 职责对齐 | 文件实际内容是否匹配 README 描述的职责 |
| 3 | 接口完整 | 类/函数签名是否齐全，参数类型和返回值是否符合 `core/types.py` 契约 |
| 4 | import 可达 | 所有 import 是否能解析（无缺失模块、无循环依赖） |
| 5 | 上下游连通 | 被调用方签名与调用方传参是否匹配 |
| 6 | 配置一致性 | 配置项是否统一从 `config/default.yaml` 或 `core/config.py` 获取；是否存在硬编码路径；是否支持 `CC_DATA_ROOT` 覆盖 |
| 7 | 文档一致性 | 文件头注释、Docstring、类型注释是否与当前实现一致 |

### 整改优先级

| 级别 | 定义 |
|------|------|
| P0 | 影响 import、运行或主链路 |
| P1 | 接口、职责或数据契约问题 |
| P2 | 代码规范、注释、文档等优化项 |

### 产出

1. 逐文件审计表（状态：✅ 已对齐 / ⚠️ 需补齐 / ❌ 缺失 + 优先级）
2. 模块依赖关系图（Import / 调用关系）
3. P0/P1/P2 整改清单，作为第二阶段整改依据

### 不做的事

- 不修改算法逻辑
- 不重构目录结构
- 不改变公共接口签名（除非存在明显设计缺陷，需先报告）

---

## §3 第二阶段：依赖顺序补齐

### 执行顺序

```
core → engine → scenes → algorithms → cloud → ml → experiments → visualization → api → examples → tests
```

### 每个模块的整改流程

1. 对照审计表，修复该模块所有 P0/P1 项
2. P2 项仅在不增加风险时顺手修复，否则记录留后
3. 完成后立即验证：`python -c "import <module>"` + 该模块相关测试
4. 报告：修改内容、修改原因、对下游模块的影响

### 模块完成判定（六项全部满足才进入下一模块）

- [ ] 模块职责与 README 一致
- [ ] 对外接口已稳定
- [ ] 上游模块可正常调用
- [ ] 不要求下游模块修改接口即可继续开发
- [ ] 无新增循环依赖
- [ ] 配置统一，不存在硬编码路径

### 各模块补齐要点

| 模块 | 补齐目标 |
|------|----------|
| `core/` | types.py 数据契约完整；config.py 支持 YAML 加载 + CC_DATA_ROOT 覆盖 |
| `engine/` | runner.py 单次仿真生命周期完整；traci_bridge.py 读写桥接签名齐全；collector.py CSV 采集可用 |
| `scenes/` | registry.py 20 路口发现；variant.py 流量倍率生成；timing_loader.py Excel 配时读取 |
| `algorithms/` | base.py ABC 接口；fixed_time / rule_adaptive 可运行；ca_max_pressure 最小决策 + TODO 扩展点 |
| `cloud/` | cloud_policy.py CloudCoordinator 签名完整，EWMA predict 返回合理默认值 |
| `ml/` | train / features / evaluate 可 import，统一函数签名，返回 mock 值 |
| `experiments/` | runner.py 批量跑批签名；metrics.py 指标计算函数齐全 |
| `visualization/` | plots.py 四种图表函数可调用（无数据时不崩溃） |
| `api/` | server.py FastAPI 启动，/health /scenes /run /status 四端点返回 mock |
| `examples/` | run_demo.py 完整调用链：config → scene → engine → algorithm → cloud → collector → metrics → 输出 |
| `tests/` | 覆盖接口契约，pytest 全绿 |

### CA-MP 最小实现策略

```python
def step(self, state: JointState) -> List[ControlAction]:
    # TODO: 容量归一化压力 (README §核心算法 改进1)
    # TODO: 溢出门控 (README §核心算法 改进2)
    # TODO: 云端动态绿灯分配 (README §核心算法 改进3)

    # MVI：选排队最长的相位，给固定绿灯时长
    best_phase = max(state.queues, key=lambda d: state.queues[d].queue_length)
    return [ControlAction(tls_id=state.tls_id, action_type="set_phase",
                          value=best_phase, reason="MVI: 最大排队相位")]
```

接口面向最终形态（`step(state: JointState) -> List[ControlAction]`），后续只需替换 `step()` 内部逻辑。

### MVI 与正式实现解耦

- 当前目标是验证接口和调用链，不是验证算法效果
- `step()` 采用简单、稳定、可预测的最小决策逻辑
- README 三项创新仅保留 TODO 和扩展点，不提前实现

### 冲突处理

若发现 README 与代码存在结构性冲突：暂停当前模块 → 输出冲突分析、影响范围及建议方案 → 等用户确认 → 再继续。不擅自修改整体架构。

---

## §4 第三阶段：动态验证

### 验证顺序

| # | 验证项 | 命令 | 通过标准 |
|---|--------|------|----------|
| 1 | 静态 import | `python -c "import core, engine, scenes, algorithms, cloud, ml, experiments, visualization, api"` | 无 ImportError |
| 2 | 单元测试 | `python -m pytest tests/ -v` | 全部 PASSED |
| 3 | 动态 Demo | `python examples/run_demo.py 1 ca_maxpressure` | 完整走通调用链，无异常，有结果打印 |
| 4 | 固定配时示例 | `python examples/run_fixed_time.py 1`（若有 SUMO） | 3600 步完成，输出 CSV |
| 5 | API 启动 | `uvicorn api.server:app --host 127.0.0.1 --port 8000` | 启动无报错 |
| 6 | API 端点 | GET /health, GET /scenes, POST /run, GET /status, GET /docs | 返回合理 JSON / 200 |
| 7 | 配置验证 | 加载 default.yaml；设置 CC_DATA_ROOT 覆盖；缺失配置时报错明确 | 无硬编码路径，跨环境可运行 |

### 配置验证

- `config/default.yaml` 能正常加载
- `CC_DATA_ROOT` 环境变量覆盖生效
- 所有路径均来自配置，不存在硬编码
- 配置缺失时给出明确错误信息，而不是程序崩溃

### 日志验证

动态验证过程中输出统一日志，至少包含：

- 当前场景
- 当前算法
- 当前运行模式（Mock / SUMO）
- 每个阶段开始与结束
- 错误信息（如有）
- 最终运行摘要

使用 Python `logging` 模块，格式统一。

### Mock 与真实环境兼容

- 动态 Demo 默认使用 Mock 数据
- 若检测到 SUMO 环境存在，支持切换至真实仿真，无需修改业务代码
- Mock 模式与 SUMO 模式共用同一套调用链
- 差异仅体现在底层 Engine 实现
- 上层算法、Cloud、Collector、Metrics 等模块无需修改

### 失败处理

- 验证不通过时，定位到具体模块，回退到第二阶段修复，修复后重新验证
- 不跳过失败项，不标记为"已知问题"留后

---

## §5 执行协议与最终交付

### 执行协议

| 规则 | 说明 |
|------|------|
| 分批整改 | 按模块逐个进行，不一次性改大量文件 |
| 逐模块验证 | 每完成一个模块，执行 import + 相关测试 + 六项完成判定，通过后再进下一个 |
| 模块报告 | 每模块完成后输出：修改内容、修改原因、对下游影响 |
| 冲突暂停 | README 与代码结构性冲突 → 暂停 → 报告 → 等确认 → 再继续 |
| 向后兼容 | 不改公共接口/目录/命名，除非有明显缺陷且先报告 |
| 日志统一 | 所有模块使用 Python `logging`，格式统一 |
| 配置统一 | 路径和参数来自 `config/default.yaml` + `core/config.py`，支持 `CC_DATA_ROOT` 覆盖 |
| Mock/SUMO 同链 | 差异仅在 Engine 底层实现，上层模块零修改即可切换 |

### Git 提交规范

按模块提交，Commit 格式：

```
feat(core): complete data contracts
feat(engine): finish runner skeleton
feat(api): add FastAPI mock endpoints
test(examples): add run_demo validation
docs(readme): synchronize project documentation
```

每个 Commit 对应一个模块或一个独立功能，避免一次性提交大量无关修改。

### 最终交付产出

1. **整改后的代码**——所有模块接口闭环、可运行
2. **验证结果汇总表**——每项通过/失败 + 输出摘要
3. **模块完成度统计**——各模块状态（✅ 闭环 / ⚠️ 有 P2 遗留）
4. **遗留问题清单**——仅 P2 优化项，不允许遗留 P0/P1
5. **后续开发建议**——正式实现 CA-MP、EWMA 训练、真实 SUMO 联调、API 业务逻辑等

### Definition of Done

项目同时满足以下条件，才视为本阶段完成：

- [ ] README 与实际代码保持一致
- [ ] 所有模块职责符合设计
- [ ] 所有公共接口已冻结且统一
- [ ] Mock 调用链完整跑通
- [ ] API 可正常启动并提供基础端点
- [ ] pytest 全部通过
- [ ] 不存在 P0、P1 遗留问题
- [ ] 代码具备直接进入核心算法开发阶段的条件，无需再次调整整体架构

---

## 附录：API 端点规格

| 方法 | 路径 | 功能 | 返回 |
|------|------|------|------|
| GET | `/health` | 健康检查 | `{"status": "ok"}` |
| GET | `/scenes` | 场景列表 | 场景 ID + 名称列表（来自 registry 或 mock） |
| POST | `/run` | 启动一次仿真 | `{"run_id": "...", "status": "started"}` |
| GET | `/status` | 当前运行状态 | `{"run_id": "...", "status": "idle/running/done"}` |
| GET | `/docs` | Swagger 自动文档 | FastAPI 自动生成 |

## 附录：ML 模块签名

```python
# ml/features.py
def extract_features(state: JointState, window: int = 5) -> dict: ...

# ml/train.py
def train(features: dict, labels: dict, alpha: float = 0.3) -> dict: ...
def predict(model: dict, features: dict) -> float: ...

# ml/evaluate.py
def evaluate(predictions: list, actuals: list) -> dict: ...  # {"mae": ..., "rmse": ...}
```

当前返回 mock 数据或默认值，不要求真正训练模型。
