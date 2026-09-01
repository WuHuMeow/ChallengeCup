# Task 5 实现报告：seconds-first 时间合同

## 修改文件

- `core/timebase.py`：新增 `SimulationWindow`、`steps_for_seconds`、`seconds_for_steps`。窗口要求 `duration_seconds > warmup_seconds >= 0`；秒转步使用向上取整，保证不会提前结束。
- `core/run_models.py`：`RunRequest` 默认保存 3600 秒运行时长和 600 秒预热时长；`step_length_override` 存在时才派生兼容 `steps`，显式 `steps` 仍保留给测试/烟测。
- `api/models.py`：API 请求增加 `duration_seconds`、`warmup_seconds`、`step_length_override`，`steps` 默认改为 `None` 并原样适配领域模型。
- `config/default.yaml`：增加 simulation/smoke/experiments 默认合同；默认时长 3600 秒、预热 600 秒、quick 600 秒、smoke 100 步、正式种子 `[42, 43, 44]`，流量等级为 normal=1.0、high=1.25。
- `experiments/tuning.py`：调优请求改用秒数默认值；高流量倍率改为 1.25；校准/holdout 种子为 `(42)` / `(43, 44)`。
- `experiments/runner.py`：CLI 和批量入口默认不生成步数；保留显式 `--steps` 兼容项，新增秒数参数。
- 对应测试：`tests/test_timebase.py`、`tests/test_run_models.py`、`tests/test_experiments.py`、`tests/test_tuning.py`。

## TDD 证据

### RED

1. 新增时间合同测试后运行：
   `\.venv\Scripts\python.exe -m pytest tests/test_timebase.py tests/test_run_models.py tests/test_experiments.py -q`
   结果：收集失败，`ModuleNotFoundError: No module named 'core.timebase'`。
2. 调优默认合同测试先于修正调优常量运行：
   `\.venv\Scripts\python.exe -m pytest tests/test_tuning.py::test_tuning_grid_and_seed_split_are_exact tests/test_tuning.py::test_tuning_request_uses_seconds_and_high_formal_traffic_level -q`
   结果：`2 failed`，实际仍为 holdout `(123, 456)` 与倍率 `1.5`。

### GREEN / 聚焦测试

- `\.venv\Scripts\python.exe -m pytest tests/test_timebase.py tests/test_run_models.py tests/test_experiments.py tests/test_tuning.py -q`
- 结果：`50 passed`。
- API、运行服务和调优回归：`\.venv\Scripts\python.exe -m pytest tests/test_api.py tests/test_api_contract.py tests/test_tuning.py tests/test_run_service.py -q`，结果 `35 passed`。

### 全量测试

- `\.venv\Scripts\python.exe -m pytest -q`
- 结果：`292 passed`。
- 中途并行运行 pytest 曾因 Windows 临时目录竞争触发 fixture 错误；串行重跑聚焦和全量均通过，最终结果以串行证据为准。

## 保护输入验证

- `赛题资料.7z` 未被修改、暂存或纳入提交；当前 SHA-256：`12A6F2FD69ACBCBF38C286A84232C4BE64000EDAF06C61FF6D3B3E09F8995C0F`。
- `data/intersection_data/` 文件数仍为 163，未出现在 diff 中。

## Self-review

- 正式请求默认不再携带全局固定步数；只有显式 `steps` 或 `step_length_override` 才能得到兼容步数。
- 迁移算法边界和 Task 3/4 的注册表、movement 合同未改动。
- `steps_for_seconds` 的 ceil 行为覆盖非整除步长，且时间输入拒绝非有限值和非正步长。
- `experiments/runner.py` 的改动是直接消费者的最小兼容修改：CLI 仍接受显式 `--steps`，但默认使用秒数。

## 关注点与边界裁决

- 本任务按简报不实现 `step-length` 场景清单解析、SimulationRunner 按秒终止或正式原子 `manifest.json` 写入；这些接口归 Task 12-13。当前旧 Runner 在收到没有兼容 `steps` 的请求时仍有历史回退路径，后续任务必须在场景解析后显式传入派生步数，不能恢复全局 36000 步默认。
- `tests/test_tuning.py` 中 PDF matrix 的显式 36000 步断言属于现有 Task 14 兼容路径，不代表新的 RunRequest 默认值。

## Fix Round 1

独立审查指出默认秒制请求仍会将 `None` 传入旧 Runner、variant fallback 仍为 1.5，以及 CLI 未拒绝 NaN/Inf。已完成最小修复：

- `engine/run_service.py` 在场景边界解析当前 sumocfg 的 `<step-length>`；优先级为显式 `steps`、`step_length_override`、场景配置，随后用 `steps_for_seconds` 派生请求步数。缺失 step-length 按已有 SUMO 约定使用 1.0，非法配置显式失败，不再静默回退 36000。
- `scenes/variant.py` 的缺失配置 fallback 和模块文档统一为 high=1.25。
- `experiments/runner.py` 对 flow/duration/warmup 使用 `math.isfinite` 校验。
- 新增真实回归覆盖 0.1 秒场景（scene 12 -> 36000 步）、1.0 秒临时 sumocfg（-> 3600 步）、variant fallback 和 NaN/Inf CLI 参数。

### Fix Round 1 TDD / Verification

- RED：新增修复测试运行结果为 `8 failed, 6 passed`，失败分别表现为 `None` 传入 Runner、fallback=1.5 和 NaN/Inf 未被拒绝。
- GREEN 聚焦：`\.venv\Scripts\python.exe -m pytest tests/test_run_service.py::test_run_service_derives_steps_from_tenth_second_scene_window tests/test_run_service.py::test_run_service_derives_steps_from_one_second_step_length tests/test_variants.py::test_variant_generator_uses_seconds_first_high_level_fallback tests/test_experiments.py::test_parse_args_rejects_invalid_dimensions -q`，结果 `14 passed`。
- Fix Round 1 聚焦回归：`\.venv\Scripts\python.exe -m pytest tests/test_timebase.py tests/test_run_models.py tests/test_experiments.py tests/test_tuning.py tests/test_variants.py tests/test_run_service.py -q`，结果 `69 passed`。
- Fix Round 1 全量：`\.venv\Scripts\python.exe -m pytest -q`，结果 `301 passed`。

修复仍遵守边界：按秒完整终止状态机和原子 manifest 继续归 Task 12-13；本轮只桥接请求到现有 Runner 的场景步长边界。
