# Task 7 Report: 保留源数据的交通与扰动变体

## 范围

- 新增 `DisturbanceSpec` 与 API adapter，覆盖施工占道、大型活动需求和车辆故障。
- `VariantGenerator` 从源 flow 就地派生并只缩放一次，记录父 flow SHA-256、输入来源、参数和扰动。
- 生成后的 bundle 运行 `validate_variant()`；失败时删除本次生成物，避免留下可运行半成品。
- 未写入官方场景目录或压缩包。

## TDD 记录

- RED 1：`tests/test_disturbances.py` 无法导入 `DisturbanceSpecModel`。
- GREEN 1：实现最小 API/domain 合同和三类 XML 后，变体与扰动测试 `11 passed`。
- RED 2：活动需求文件缺少命名 route，回归测试失败。
- GREEN 2：加入固定 `event_demand_route` 后，指定五组回归 `38 passed`。

## 验证

- 指定回归：`tests/test_disturbances.py tests/test_variants.py tests/test_run_models.py tests/test_api.py tests/test_run_service.py` -> `38 passed`。
- 官方预检：20/20 场景均生成施工变体，父 flow 哈希与来源记录一致。
- 全量 pytest：`324 passed in 35.17s`。
- `git diff --check`：通过，仅有既有 CRLF 转换提示。
- 保护输入：`赛题资料.7z` SHA-256 为 `12a6f2fd69acbcbf38c286a84232c4be64000edaf06c61ff6d3b3e09f8995c0f`；`data/intersection_data` 无差异。

## 提交

- `9439f92` (`feat: add auditable traffic disturbances`)

## Review 修复第 1 轮

### 根因

复审沿 `VariantGenerator -> RunService -> SimulationRunner -> TraCIBridge` 跟踪确认：旧实现把缩放 flow 作为 `-a` 追加文件，但运行器仍通过父 `sumocfg` 加载完整原始 `.rou.xml`。因此 SUMO 实际加载了父车辆和缩放流量两套需求。活动扰动还引用了未定义的 `passenger` 车型；施工和故障则是同一 lane-close XML，未使用强度。

### 修复

- 变体先用 `jtrrouter` 从唯一缩放 flow 派生 `derived_demand.rou.xml`，再写入临时 `variant.sumocfg`，其 `route-files` 只能指向该派生路由；中间 flow 不再放入 SUMO additional 参数。
- RunService 将派生运行配置传给 SimulationRunner，后者不再用增强父配置覆盖该配置。
- `VariantBundle` 记录运行配置、派生路由与路网上下文；`validate_variant()` 解析所有 runtime/additional XML，校验车型、路由、边、车道、ID、时间区间、文件冲突和唯一派生人口。
- `_scale_tree()` 同时派生 `<vehicle>` 的 ID/type；flow 与 vehicle 不再保留未缩放原定义。
- construction 用强度缩短封道时间；event_demand 用强度缩放 `360 veh/h` 的可解析活动车型和路由；vehicle_failure 生成安全停车车辆，并用强度缩短停车时长。manifest 写明各类型的强度物理语义。
- manifest 中来源路径使用仓库相对路径，不保留工作区绝对路径。

### TDD 记录

- RED 1：新增运行配置、混合 flow/vehicle、坏 additional 引用和扰动强度测试，`5 failed, 8 passed`；失败点分别为无派生 config、vehicle 未派生、校验只解析主 flow、施工/故障未使用 intensity。
- GREEN 1：引入派生 route/sumocfg 和全输入校验后，临时 fixture 无法用 jtrrouter 派生，重建为真实官方路网 fixture；随后聚焦 `26 passed`。
- RED 2：强度超过 1 的施工规格被接受，`1 failed`。
- GREEN 2：施工/故障强度限制为 `(0, 1]`，聚焦四组回归 `35 passed`。
- RED 3：篡改运行配置指回父 `.rou.xml` 后校验未报错，`1 failed`。
- GREEN 3：校验运行配置仅可引用 `derived_demand.rou.xml`，聚焦四组回归 `37 passed`。
- RED 4：manifest 未冻结强度物理语义，三个扰动测试均 `KeyError`。
- GREEN 4：记录 `intensity_semantics`，更广聚焦 `73 passed`。

### SUMO Smoke

使用 `sumo -c variant.sumocfg -a <additional> --end 4 --no-step-log true`，开始/结束区间为 1 至 3 秒：

- construction：exit `0`，stderr 空。
- event_demand：exit `0`，stderr 空。
- vehicle_failure：exit `0`，stderr 空。

### 最终验证

- 聚焦：`tests/test_disturbances.py tests/test_variants.py tests/test_run_models.py tests/test_api.py tests/test_run_service.py tests/test_resilience.py tests/test_traci_outputs.py` -> `73 passed in 37.24s`。
- 全量：`pytest -q -p no:cacheprovider --basetemp=D:\WorkPlace\t7full` -> `335 passed in 78.26s`。
- 系统 Python `3.14.7`：`compileall -q algorithms api cloud core engine experiments ml scenes scripts visualization` -> exit `0`。
- `git diff --check` 通过（仅 CRLF 提示）。
- 保护输入：`赛题资料.7z` SHA-256 仍为 `12a6f2fd69acbcbf38c286a84232c4be64000edaf06c61ff6d3b3e09f8995c0f`；官方数据仍为 `163` 个 Git 跟踪文件，保护路径无 diff。

### 提交

- `dede66f` (`fix: isolate derived variant demand`)
- `662b046` (`docs: record task 7 review fix evidence`)

## Review 修复第 2 轮

### 根因

- `validate_variant()` 只遍历根级 demand，嵌套在 calibrator 下的 flow 可绕过 ID、车型、路由和区间校验；rerouter/calibrator/closing lane 目标也未验证。
- 运行配置只比较 route basename，未按 sumocfg 所在目录解析 net/route 实际路径，也未拒绝配置内重新引入的 additional-files。
- event_demand 同时缩短活动时间窗并缩放流率，使总增量需求按 intensity 的平方缩放。
- 派生配置固定命名为 `variant.sumocfg`，`TraCIBridge` 无法从文件名解析 `demo_<id>`，因此 edge mapping 回退。
- `_write_runtime_config()` 删除父配置的整个 `<output>`，scene 11 的 queue-output 能力随之丢失。

### 修复

- 对中间 flow、派生 route 和所有 additional XML 执行嵌套 demand、非空/唯一 ID、车型/命名 route、from/to、depart、区间、route edge 与网络连通性校验；运行人口去重排除未被 SUMO 加载的中间 flow。
- 校验 rerouter edge、calibrator edge、closingLaneReroute lane 和 stop lane；sumocfg 的 net/route 路径必须解析到 bundle 的精确文件，配置内不得额外声明 additional-files。
- event_demand 保留完整声明窗口，仅以 `360 veh/h * intensity` 缩放流率；construction 和 vehicle_failure 继续以 intensity 缩放持续时长。
- 派生配置改为 `<父配置 stem>_variant.sumocfg`，保留 `demo_<id>` 身份；父 `<output>` 原样保留，源配置字节不变。
- RunService 经真实 SimulationRunner/TraCIBridge 启动边界验证：scene 1 派生配置成功应用进口道筛选和 lane direction mapping；scene 11 的命令继续重定向 queue-output 到运行 artifacts。

### TDD 记录

- RED 1：嵌套 event flow、重复 demand ID、扰动目标、运行配置实际路径/additional-files 和 event 精确强度语义新增测试。

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_disturbances.py -q -p no:cacheprovider --basetemp=D:\WorkPlace\t7r2-red-resume2
  # 12 failed, 18 passed in 38.65s
  ```

- GREEN 1：实现嵌套/引用/路径/目标校验和 event 窗口修复。

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_disturbances.py -q -p no:cacheprovider --basetemp=D:\WorkPlace\t7r2-green1b
  # 30 passed in 38.96s
  ```

- RED 2：派生配置身份、父 output、scene 11 queue-output 和 RunService edge mapping 调用链。

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_variants.py::test_runtime_config_preserves_scene_identity_and_parent_output tests/test_traci_outputs.py::test_scene_11_variant_keeps_configured_queue_output_redirect tests/test_run_service.py::test_run_service_passes_complete_variant_bundle_to_runner tests/test_run_service.py::test_run_service_variant_applies_edge_mapping_through_real_runner -q -p no:cacheprovider --basetemp=D:\WorkPlace\t7r2-red-config2
  # 4 failed in 4.21s
  ```

- GREEN 2：保留 output 并采用 scene-aware 配置名。

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_variants.py::test_runtime_config_preserves_scene_identity_and_parent_output tests/test_traci_outputs.py::test_scene_11_variant_keeps_configured_queue_output_redirect tests/test_run_service.py::test_run_service_passes_complete_variant_bundle_to_runner tests/test_run_service.py::test_run_service_variant_applies_edge_mapping_through_real_runner -q -p no:cacheprovider --basetemp=D:\WorkPlace\t7r2-green-config
  # 4 passed in 4.81s
  ```

- RED 3：未知 from/to、非有限 depart 和已知但不连通 route。

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_disturbances.py -q -k "unknown_intermediate_flow_edge or invalid_runtime_vehicle_depart or disconnected_route_edges" -p no:cacheprovider --basetemp=D:\WorkPlace\t7r2-red-demand
  # 4 failed, 30 deselected in 4.31s
  ```

- GREEN 3：加入对应最小校验。

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_disturbances.py -q -p no:cacheprovider --basetemp=D:\WorkPlace\t7r2-green-demand
  # 34 passed in 30.53s
  ```

### SUMO Smoke

使用真实 TraCI/SUMO 1.27.1 读取扰动运行状态，而非只检查 XML 可解析：

- construction：t=2 时 `E0_0` 仅允许 authority，t=4 时恢复开放。
- event_demand：t=4 时 calibrator 仍存在，begin/end 为 `1/5`，流率为 `180 veh/h`；该时点已超过旧错误实现的缩短窗口。
- vehicle_failure：故障车辆在 60 秒真实仿真窗口内进入 stopped 状态。
- 三项 smoke：

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_disturbances.py -q -k "activates_and_releases_lane or remains_active_for_full_window or reaches_active_stop" -p no:cacheprovider --basetemp=D:\WorkPlace\t7r2-sumo-probe
  # 3 passed, 31 deselected in 6.06s
  ```

### 最终验证

- 聚焦：

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_disturbances.py tests/test_variants.py tests/test_run_service.py tests/test_resilience.py tests/test_traci_outputs.py -q -p no:cacheprovider --basetemp=D:\WorkPlace\t7r2-focused2
  # 74 passed in 47.23s
  ```

- 全量：

  ```powershell
  .\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=D:\WorkPlace\t7r2-full
  # 354 passed in 74.28s
  ```

- 系统 Python `3.14.7`：

  ```powershell
  & 'C:\Users\peng\AppData\Local\Programs\Python\Python314\python.exe' --version
  # Python 3.14.7
  & 'C:\Users\peng\AppData\Local\Programs\Python\Python314\python.exe' -m compileall -q algorithms api cloud core engine experiments ml scenes scripts visualization
  # exit 0
  ```

- 差异格式：

  ```powershell
  git diff --check
  git diff --cached --check
  # exit 0
  ```

- 保护输入：`赛题资料.7z` SHA-256 仍为 `12a6f2fd69acbcbf38c286a84232c4be64000edaf06c61ff6d3b3e09f8995c0f`，保持未跟踪/未暂存；`data/intersection_data` 仍为 `163` 个 Git 跟踪文件且无任务差异。

  ```powershell
  Get-FileHash -LiteralPath '赛题资料.7z' -Algorithm SHA256
  (git ls-files -- 'data/intersection_data' | Measure-Object).Count
  git diff --name-only -- 'data/intersection_data'
  git diff --cached --name-only
  # SHA-256 12A6F2FD69ACBCBF38C286A84232C4BE64000EDAF06C61FF6D3B3E09F8995C0F
  # 163 tracked files; protected data diff empty; archive absent from staged names
  ```

### 提交

- `08b7be1` (`fix: validate executable disturbance bundles`)
