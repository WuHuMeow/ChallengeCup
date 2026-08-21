# Algorithms

## 模块职责

`algorithms/` 实现统一交通控制器契约：

| 文件 | 策略 |
|---|---|
| `base.py` | `BaseControlAlgorithm` 抽象接口 |
| `fixed_time.py` | SUMO/Excel 固定配时基线 |
| `rule_adaptive.py` | 基于排队和绿灯约束的感应控制 |
| `ca_max_pressure.py` | 相位感知的 Capacity-Aware MaxPressure |

所有算法实现：

```python
init(scene)
step(state) -> list[ControlAction]
reset()
name
```

算法只输出决策，不直接调用 TraCI。Runner 将动作交给唯一的
`SafetyExecutor.apply()` 边界；执行器返回与算法原始请求关联的
`tuple[ActionResult, ...]`，并独占 bridge 的私有信号写入端。

## CA-MP

当前 CA-MP 从 `JointState.phase_states` 读取真实 SUMO 相位拓扑，输出合法整数相位：

1. 上游与下游排队按各自容量归一化；
2. 预测到达量按 `prediction_weight` 加入压力；
3. 下游占用率达到 `overflow_occupancy_threshold` 时阻断该相位；
4. 在最大绿灯到期时寻找替代相位，并输出最终绿灯请求；
5. `SafetyExecutor` 执行最小绿灯约束并插入真实黄灯/全红相位；
6. 绿灯时长按压力动态缩放到 `min_green..max_green`；
7. `reset()` 清理控制器配置和云策略状态。

参数来自 `config/default.yaml::algorithms.ca_maxpressure`，运行级覆盖只允许：

- `overflow_occupancy_threshold`
- `prediction_weight`
- `base_green`

## 校准与留出

`experiments/tuning.py` 对路口 1、11、16 的种子 42 做参数搜索，冻结赢家后仅用种子
123、456 做留出评估。结果写入 `selected_params.json`、`tuning_results.csv` 和
`holdout_summary.json`。

```powershell
python scripts/run_pdf_matrix.py --quick --tune `
  --output-root output/runs/tuning-quick
python scripts/run_pdf_matrix.py --steps 36000 `
  --output-root output/runs/matrix-full
```

上述命令在运行时创建指定的输出根目录；这些目录不随仓库保留。每个算法运行产物位于：

```text
<root>/i{id}/{algorithm}/x{flow}/s{seed}/{run_id}/
```

## 依赖与边界

- 共享类型：`core.types`、`core.run_models`
- 配置：`core.config`
- 云端预测/参数：`cloud.CloudPolicy`
- 相位交通状态：由 `engine.traci_bridge` 从真实 tlLogic 和车道拓扑构建
- 原始 `data/intersection_data/` 只读

主办方原始 J2 信号方案可能触发 SUMO unsafe/unused-state warning；算法运行证据应同时记录
终态和源数据 warning。

已记录的 360 次矩阵审计为通过状态，但对应的大型生成产物已清理。不要为恢复历史文件而重新运行
完整矩阵；Docker live 和第二机器复现仍是 `not_run` 的独立证据轴。
