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
