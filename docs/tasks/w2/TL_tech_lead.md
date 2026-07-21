# Tech Lead W2 任务书

> 周期：7/27–8/2 | 核心目标：完成云-边-端联调，三种算法在路口 1 出对比数据

## 本周背景

本周首次引入云-边-端联调：CloudPolicy（`cloud/cloud_policy.py`）用 EWMA（指数加权移动平均）预测未来流量，公式为 `predicted(t+1) = α × observed(t) + (1-α) × predicted(t)`，α=0.3。预测结果通过 `PredictionResult` 传给 CA-MP 算法修正压力计算。你需要验证这条数据链路（CloudPolicy.predict → CA-MP.step → ControlAction）端到端跑通。

## 每日任务

### Day 1（7/27）

- [ ] 检查 W1 交付物完整性：IA 的 20 路口迁移、IB 的 engine 模块、AA/AB 的算法、EX 的实验框架是否全部合入
- [ ] 解决 W1 遗留的集成问题（如有）
- [ ] 确认 `experiments/runner.py` 的 `run_batch()` 支持 `fixed_time`、`actuated`、`ca_maxpressure` 三种算法
- [ ] 确认 `run_batch()` 支持 `seeds` 和 `levels` 参数

**验证：** `python -c "from experiments.runner import run_batch, ALGORITHM_MAP; print(list(ALGORITHM_MAP.keys()))"` → 输出 `['fixed_time', 'actuated', 'ca_maxpressure']`

### Day 2（7/28）

- [ ] 协调 IB 确认 `run_batch()` 的 `output_root` 参数正确生成目录结构
- [ ] 在路口 1 上单次运行 CA-MP：调用 `run_batch(intersection_ids=["1"], algorithms=["ca_maxpressure"], seeds=[42], steps=3600)`
- [ ] 确认输出目录下生成 CSV 文件且包含有效数据（非全零）
- [ ] 检查 CloudPolicy 是否被正确调用（日志中有 EWMA 预测输出）

**验证：** `python -c "from experiments.runner import run_batch; r = run_batch(intersection_ids=['1'], algorithms=['ca_maxpressure'], seeds=[42], steps=100); print(r[0]['csv'])"` → 输出 CSV 路径，文件存在且有数据行

### Day 3（7/29）

- [ ] 在路口 1 上跑三种算法完整对比（各 3600 步，seed=42）
- [ ] 记录三种算法的 avg_travel_time 和 avg_queue_length
- [ ] 验证 CA-MP 的平均行程时间 < 固定配时（如不满足，与 AB 排查）
- [ ] 将对比数据发给 DA（报告素材）和 DB（图表素材）

**验证：** `python -c "from experiments.runner import run_batch; r = run_batch(intersection_ids=['1'], seeds=[42], steps=3600); print(len(r), '组完成')"` → 输出 `3 组完成`

### Day 4（7/30）

- [ ] Review AB 的 CA-MP 代码：溢出门控逻辑（占用率 > 0.9 强制放行）、容量计算（queue_length / capacity）、边界处理（无车时返回空列表）
- [ ] Review IB 的云-边-端消息流：JointState 每步产生、CloudPolicy.predict() 被调用、PredictionResult 传入算法
- [ ] 提出修改意见，记录到 Issue 或文档中
- [ ] 跟踪修复进度

**验证：** `python -m pytest tests/test_algorithms.py tests/test_cloud.py -v` → 全部 passed

### Day 5（7/31）

- [ ] 在路口 16（24m 短边）上验证三种算法：关注溢出门控是否在短边上触发
- [ ] 在路口 11（0.1s 步长）上验证：确认决策频率正确（不会每 0.1s 切一次相位）
- [ ] 记录问题并与 AB/IB 修复
- [ ] 确认修复后重新跑通

**验证：** `python -c "from experiments.runner import run_batch; r = run_batch(intersection_ids=['16'], algorithms=['ca_maxpressure'], seeds=[42], steps=3600); print('路口16完成')"` → 无报错

### Day 6（8/1）

- [ ] 打 tag：`git tag v0.2-w2-complete`
- [ ] 编写 W2 周报
- [ ] 确认 W3 前置条件：`run_batch()` 能生成 20×3×2×3=360 组实验、输出目录结构正确
- [ ] 与 EX 确认 W3 第一天能开始批量跑实验

**验证：** `python -c "from experiments.runner import run_batch; import itertools; total = len(list(itertools.product(range(20), ['fixed_time','actuated','ca_maxpressure'], ['normal','high'], [42,123,456]))); print(total)"` → 输出 `360`

### Day 7（8/2）

- [ ] 处理本周遗留 bug
- [ ] 规划 W3 实验运行顺序（先跑哪些路口、是否需要分批）
- [ ] 确认 DA/DB 的 W2 产出（报告框架更新、图表测试）

**验证：** `git tag -l "v0.2*"` → 输出 `v0.2-w2-complete`

## 关键代码指引

```python
# 批量实验入口（完整实现见 experiments/runner.py）
ALGORITHM_MAP = {
    "fixed_time": FixedTimeAlgorithm,
    "actuated": RuleAdaptiveAlgorithm,
    "ca_maxpressure": CAMaxPressureAlgorithm,
}

def run_batch(
    intersection_ids: List[str] | None = None,  # 默认全部 20 个
    algorithms: List[str] | None = None,         # 默认三种
    levels: List[TrafficLevel] | None = None,    # 默认 [NORMAL, HIGH]
    seeds: List[int] | None = None,              # 默认 [42, 123, 456]
    steps: int = 3600,
    output_root: Path | None = None,
) -> List[Dict[str, str]]:
    # 对每个 (路口, 算法, 流量等级, 种子) 组合创建 SimulationRunner 并运行
    # 返回 [{"intersection_id": "1", "algorithm": "ca_maxpressure", "seed": "42", "csv": "..."}]
    ...
```

```python
# EWMA 预测（完整实现见 cloud/cloud_policy.py）
class CloudPolicy:
    def __init__(self):
        self.alpha = 0.3       # 平滑系数：平衡响应速度与稳定性
        self.horizon = 300     # 预测时域（秒）
        self._prev_predicted = {}

    def predict(self, state: JointState) -> PredictionResult:
        predicted = {}
        for direction, observed in state.flows.items():
            prev = self._prev_predicted.get(direction, observed)
            predicted[direction] = self.alpha * observed + (1 - self.alpha) * prev
        self._prev_predicted = predicted
        return PredictionResult(
            horizon_steps=self.horizon,
            horizon_seconds=float(self.horizon),
            predicted_flows=predicted,
        )
```

```python
# CA-MP 如何接入云端预测（完整实现见 algorithms/ca_max_pressure.py）
class CAMaxPressureAlgorithm(BaseControlAlgorithm):
    def __init__(self, cloud_policy: CloudPolicy | None = None):
        self.cloud_policy = cloud_policy or CloudPolicy()
        self.overflow_threshold = 0.9   # 溢出门控阈值
        self.base_green = 30            # 云端下发的基础绿灯时长

    def step(self, state: JointState) -> List[ControlAction]:
        pred = self.cloud_policy.predict(state)  # 每步调用云端预测
        if not state.queues:
            return []
        # TODO(AB): 容量归一化 pressure = queue_length / capacity
        # TODO(AB): 溢出门控 occupancy > 0.9 时强制放行
        # TODO(AB): 动态绿灯 base_green * (phase_pressure / avg_pressure)
        best_queue = max(state.queues, key=lambda q: q.queue_length)
        return [ControlAction(tls_id=state.tls_id, action_type="set_phase",
                              value=best_queue.direction, reason="最大排队方向")]
```

## 交付物

| 文件 | 截止 | 验收标准 |
|------|------|----------|
| 路口 1 三算法对比数据 | Day 3 | 3 个 CSV 文件，CA-MP 的 avg_travel_time < FixedTime |
| 路口 16 验证 | Day 5 | CA-MP 跑通 3600 步无报错，溢出门控有触发记录 |
| 路口 11 验证 | Day 5 | 0.1s 步长下正常运行，无异常频繁切相位 |
| W3 前置确认 | Day 6 | `run_batch()` 可生成 360 组实验配置 |
| git tag v0.2 | Day 6 | `git tag -l "v0.2*"` 有输出 |

## 协作对接

- Day 3 将路口 1 对比数据发给 DA 和 DB
- Day 4 将 review 意见发给 AB 和 IB
- Day 6 与 EX 确认 W3 批量实验可启动
