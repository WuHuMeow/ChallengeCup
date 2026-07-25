> **（注意） 已废弃**：本设计文档（XGBoost + Webster 方案）已被 CA-MP（Capacity-Aware MaxPressure）方案取代。
> 当前项目算法方向为 CA-MP，详见 `docs/tasks/roadmap.md` 和根目录 `README.md`。
> 本文件仅作历史参考保留。

---

# XGBoost 流量预测 → Webster 适配器 · 设计文档（已废弃）

**项目**: 雄安新区"城市大脑"车路云一体化协同感知算法平台(挑战杯 2026, 编号 XH-202613, 赛道 B)
**主题**: 高级扩展方案 B —— 用 XGBoost 预测未来流量,驱动 Webster 公式动态调参
**作者**: fyx0927
**日期**: 2026-07-18
**状态**: 已废弃，被 CA-MP 方案取代

---

## 0. 摘要

将 XGBoost 短时流量预测嵌入 `cloud_policy.predict()`,预测结果送入新增的
`webster_adapter`,按 5 分钟节奏 + EMA 平滑 + 阈值过滤 + 周期边界四道防抖,
仅重算绿信比(周期允许 ±10s 微调),输出 `set_phase_duration` 控制动作
写入 SUMO。本设计不改 `core/types.py` 中既有数据契约,只新增 `WebsterPlan`
与 `AdapterStats` 两个 dataclass;不引入新依赖(已包含 xgboost/scikit-learn/joblib)。
离线训练一次产出 `ml/model.pkl`,运行期不重训。

---

## 1. 决策清单(回顾)

| # | 决策点 | 选择 | 理由 |
|---|---|---|---|
| 1 | 9.1 范围 | **A: demo_1 端到端** | 1 人 4 周可独立完成;后续 19 路口是工程复制,不是算法问题 |
| 2 | 预测粒度 | **每方向标量(veh/s)** | 契合 Webster 公式 `y_i = q_i / s_i`;XGBoost 做 tabular 回归 |
| 3 | 防抖策略 | **5 分钟节奏 + EMA + 阈值 + 周期边界** | 雄安窄路密网周期稳定优先;防单点异常 |
| 4 | 训练数据源 | **SUMO 自监督(15 次仿真)** | 特征空间最丰富;不依赖 xlsx 手工标注 |
| 5 | 加载方式 | **启动一次性 joblib.load** | 单进程仿真不需要热加载;现有 `_load_model` 已支持 |
| 6 | 调参范围 | **只调绿信比,周期 ±10s 微调** | 兼容方案 A 干线绿波的相位差按周期算 |

---

## 2. 架构与数据流

### 2.1 文件改动一览(改 5 个 + 新增 2 个)

| 文件 | 类型 | 改动内容 |
|---|---|---|
| `cloud/webster_adapter.py` | **新增** | 5 分钟节奏 + EMA + 阈值 + 周期边界,转 `predicted_flows` 为 `WebsterPlan` |
| `cloud/cloud_policy.py` | 改 | `predict()` 调 XGBoost 推理,返回真实 `PredictionResult` |
| `ml/features.py` | 改 | `extract_features()` 填实:队列+流量+时段+相位+5 分钟滑动均值 |
| `ml/train.py` | 改 | 实现 XGBoost 训练 + 交叉验证 + 保存 model.pkl |
| `algorithms/ca_max_pressure.py` | 改 | `step()` 调 CloudPolicy + WebsterAdapter,输出 `set_phase_duration` |
| `ml/evaluate.py` | 改 | 填实 RMSE/MAE/R² + 第二层端到端仿真对比 |
| `experiments/data_generator.py` | **新增** | 跑 15 次仿真(3 流量级 × 5 种子),合并产出 train.csv |

不动的文件:`core/types.py`(只在其末尾追加新 dataclass)、`engine/*`、
`scenes/*`、`algorithms/fixed_time.py`、`algorithms/rule_adaptive.py`、
`algorithms/base.py`、`api/*`、`visualization/*`、`config/*`、`docker/*`、
`core/config.py`、`docs/*`(除本文件)。

### 2.2 数据流图

```
离线阶段(一次性):
  SUMO demo_1 × 3 流量级 × 5 种子 (固定配时驱动)
      ↓ engine/collector.py
  datasets/demo_1_train.csv
      ↓ ml/train.py
  ml/model.pkl

在线阶段(每次仿真运行):
  SUMO step
      ↓ engine/traci_bridge
  JointState → algorithms/ca_maxpressure.step()
      ├── cloud/cloud_policy.predict()
      │     ├── ml/features.extract_features() → 19 维向量
      │     └── XGBoost model.predict() → predicted_flows (4 方向 veh/s)
      └── cloud/webster_adapter.update(predicted_flows, ...)
              ├── 节奏检查 (≥ 5 min?)
              ├── 阈值检查 (变化 ≥ 15%?)
              ├── EMA 平滑 (α=0.3)
              ├── Webster 公式 → 新绿信比
              └── 周期边界 ±10s
      ↓
  ControlAction(tls_id, "set_phase_duration", [(phase_idx, green_time), ...])
      ↓ engine/traci_bridge
  SUMO 写入
```

### 2.3 时序约束

| 事件 | 触发条件 | 频率 |
|---|---|---|
| WebsterAdapter 重算绿信比 | 距上次 ≥ 300s AND 流量预测变化 ≥ 15% | ≤ 每 5 分钟一次 |
| XGBoost 推理 | 每次重算触发时 | 同上(不每步跑) |
| `set_phase_duration` 写入 | 重算触发后,在下一个相位切换点 | 一次性 |

---

## 3. 数据契约

### 3.1 不动的既有类型

`core/types.py` 中 `JointState`、`PredictionResult`、`ControlAction`、`Scene`、
`SceneMeta`、`QueueState`、`TimingPlan`、`PhaseInfo`、`SimulationMetrics`、
`MetricsCallback` 全部保留原签名。

### 3.2 新增类型(追加在 `core/types.py` 末尾)

```python
@dataclass
class WebsterPlan:
    """Webster 适配器输出:一组待写入 SUMO 的相位绿信比建议。"""
    tls_id: str
    cycle_length: float                     # 单位:秒
    green_splits: List[Tuple[int, float]]   # [(phase_index, green_seconds), ...]
    yellow_times: List[Tuple[int, float]]   # 黄灯时长,通常由相位几何固定
    timestamp: float                        # 本次计算时间戳,用于去重
    reason: str                             # 调试用,如 "predicted_flow_change_18%"


@dataclass
class AdapterStats:
    """Webster 适配器运行统计,供 evaluate.py 第二层评估使用。"""
    updates_total: int                      # 实际触发的更新次数
    updates_skipped_threshold: int          # 因变化 < 阈值跳过的次数
    updates_skipped_interval: int           # 因未到 5 分钟跳过的次数
    last_update_step: int
    last_predicted_flows: Dict[str, float]
    last_green_splits: List[Tuple[int, float]]
```

### 3.3 明确拒绝的类型

- LSTM/Transformer 输出序列 —— XGBoost tabular,不需要
- 模型版本号类型 —— 单文件 model.pkl
- 多路口批量预测类型 —— 9.1 范围单路口

---

## 4. 训练流程

### 4.1 训练数据生成(`experiments/data_generator.py`)

**输入**: demo_1 SUMO 工程 + 3 个流量级(0.5x / 1.0x / 3.0x)+ 5 个随机种子

**过程**:
```
for level in [0.5, 1.0, 3.0]:
    for seed in range(5):
        run_sumo(demo_1, level, seed, duration=3600s, driver=FixedTimeAlgorithm)
        → engine/collector.py 输出 collector.csv
共 15 个 CSV,合并去 schema 差异 → datasets/demo_1_train.csv
```

**关键约束**:这次跑仿真**不接 ML 算法**,统一用固定配时基线驱动,目的是采集
"自然状态"作为训练样本,不引入算法偏见。

**输出 schema(每行)**:
```
step, sim_time, tls_id, current_phase,
queue_N, queue_S, queue_E, queue_W,
flow_N, flow_S, flow_E, flow_W,
vehicle_count,
[collector 实际产出的其他字段]
```

**风险点**: 若 `engine/collector.py` 当前不输出 `flow_*` 字段,需 Day 1 立即补。
这是 9.1 路径上的第一颗雷,不能拖。

### 4.2 特征工程(`ml/features.py`)

```python
def extract_features(state: JointState,
                     history: List[JointState],
                     current_time: float) -> np.ndarray:
    """19 维特征向量。"""

    per_direction_features = []  # 4 方向 × 4 特征 = 16
    for d in ["N", "S", "E", "W"]:
        q = get_queue_for(state.queues, d)
        f = state.flows.get(d, 0.0)
        sat = SAT_FLOW_PER_LANE[d]      # 来自 scenes/registry.py 或 scene_meta
        y_i = f / max(sat, 1e-3)        # Webster 流量比
        recent_mean = compute_recent_flow_mean(history, d, window_minutes=5)
        per_direction_features.extend([q, f, y_i, recent_mean])

    global_features = []
    hour = current_time / 3600 % 24
    global_features.extend([math.sin(2*pi*hour/24), math.cos(2*pi*hour/24)])
    global_features.append(1.0 if is_weekday(current_time) else 0.0)
    global_features.append(current_time / 3600 / 24)  # sim_time_normalized

    return np.array(per_direction_features + global_features, dtype=np.float32)


def extract_labels(future_collector_window: pd.DataFrame) -> np.ndarray:
    """标签:未来 5 分钟(300s)各方向平均 veh/s。"""
    labels = []
    for d in ["N", "S", "E", "W"]:
        total_veh = future_collector_window[f"flow_{d}"].sum()
        labels.append(total_veh / 300.0)
    return np.array(labels, dtype=np.float32)
```

### 4.3 训练(`ml/train.py`)

```
输入: datasets/demo_1_train.csv
过程:
  1. 读 CSV → 滑窗构造 (X, y) 样本
     - 窗口步长: 60s (匹配 collector 采样频率)
     - X = t 时刻 19 维特征向量
     - y = t+300s 时刻 4 方向平均流量
  2. 切分 train/val = 8:2 (固定 random_state=42,可复现)
  3. XGBoost 训练
     - objective: reg:squarederror
     - n_estimators: 300, max_depth: 6, learning_rate: 0.05
     - subsample: 0.8, colsample_bytree: 0.8
     - early_stopping_rounds: 20
  4. 在 val 集评估 RMSE / MAE / R²
  5. dump 到 ml/model.pkl (joblib)

输出:
  - ml/model.pkl
  - output/training_report.json (训练指标 + 特征重要性)
```

**不做的优化**: 不做时序建模(LSTM/Transformer);不做 grid/random search
(用轻度调参);不做 K-fold(一次切分够)。

---

## 5. 在线推理 + Webster 适配

### 5.1 `cloud/cloud_policy.py`

```python
class CloudPolicy:
    def __init__(self, model_path=None, history_buffer_size=10):
        # history_buffer_size=10: 缓存最近 10 个 JointState,
        # 满足 5min/60s = 10 步的滑动窗口
        self._history: deque = deque(maxlen=history_buffer_size)
        # ... 原 _load_model 逻辑不变

    def push_state(self, state: JointState) -> None:
        """由外部(engine 或 ca_maxpressure)在 step() 之前调用。"""
        self._history.append(state)

    def predict(self, state: JointState) -> PredictionResult:
        if self._model is None:
            return PredictionResult(            # 兜底,与原行为一致
                horizon_steps=300, horizon_seconds=300.0,
                predicted_flows=state.flows,
            )

        history = list(self._history)
        x = extract_features(state, history, current_time=state.timestamp)
        y_pred = self._model.predict(x.reshape(1, -1))[0]
        return PredictionResult(
            horizon_steps=300, horizon_seconds=300.0,
            predicted_flows={
                "N": float(y_pred[0]), "S": float(y_pred[1]),
                "E": float(y_pred[2]), "W": float(y_pred[3]),
            },
        )
```

**不改动**: `_load_model`、`__init__` 签名(向后兼容)、配置文件读取。

### 5.2 `cloud/webster_adapter.py`(新增)

```python
class WebsterAdapter:
    def __init__(
        self,
        scene_meta: SceneMeta,
        base_cycle: float,             # 路口基准周期(由 xlsx 或 SUMO 默认给出)
        cycle_min: float,              # 允许最小周期
        cycle_max: float,              # 允许最大周期
        sat_flow_per_lane: Dict[str, float],   # 各方向饱和流量
        fixed_yellow_times: List[Tuple[int, float]],
        phase_directions: Dict[int, List[str]],   # {phase_idx: ["N","S"], ...}
        total_lost_time_per_cycle: float,        # SUMO 实际损失时间(秒/周期)
        phase_min_greens: Dict[int, float],      # {phase_idx: min_green_s, ...}
        initial_green_splits: List[Tuple[int, float]],  # 由 SUMO 默认或 xlsx 给出
        alpha: float = 0.3,            # EMA 平滑系数
        change_threshold: float = 0.15,  # 流量变化阈值
        update_interval_s: float = 300.0,  # 5 分钟
    ):
        # 上述 kwargs 在 __init__ 内赋值给同名私有属性,
        # 供 update() 使用。此处省略赋值细节。
        ...

    def update(
        self,
        predicted_flows: Dict[str, float],
        current_cycle: float,
        current_green_splits: List[Tuple[int, float]],
        current_sim_time: float,
    ) -> Optional[WebsterPlan]:
        """每 5 分钟被调一次。返回 None = 跳过本轮。"""

        # 1. 节奏检查
        if current_sim_time - self._last_update_time < self.update_interval_s:
            self.stats.updates_skipped_interval += 1
            return None

        # 2. 阈值检查(相对上次实际更新,不是上次 EMA 值)
        max_change = max(
            abs(predicted_flows[d] - self._last_actual_predicted[d])
            / max(self._last_actual_predicted[d], 1e-3)
            for d in ["N", "S", "E", "W"]
        )
        if max_change < self.change_threshold:
            self.stats.updates_skipped_threshold += 1
            return None

        # 3. EMA 平滑(对原始预测做,不用 _last_actual_predicted)
        smoothed = {
            d: self.alpha * predicted_flows[d] + (1 - self.alpha) * self._last_smoothed[d]
            for d in ["N", "S", "E", "W"]
        }

        # 4. Webster 公式
        y_per_phase = compute_phase_flow_ratios(
            smoothed, self._sat_flow_per_lane, self._phase_directions
        )
        Y = sum(y_per_phase.values())
        L = self._total_lost_time_per_cycle
        C_new = (1.5 * L + 5) / max(1 - Y, 0.01)

        # 5. 周期边界:先算 C_min..C_max,再 ±10s 微调
        C_new = clip(C_new, self._cycle_min, self._cycle_max)
        if abs(C_new - current_cycle) > 10.0:
            C_new = current_cycle + 10.0 * (1 if C_new > current_cycle else -1)

        # 6. 绿信比分配(按 y_i / Y 比例,保最小绿灯)
        green_splits = allocate_green_time(
            C_new, y_per_phase, self._phase_min_greens
        )

        # 7. 写状态 + 返回
        self._last_update_time = current_sim_time
        self._last_actual_predicted = predicted_flows
        self._last_smoothed = smoothed
        self.stats.updates_total += 1
        self.stats.last_update_step = int(current_sim_time)
        self.stats.last_predicted_flows = smoothed
        self.stats.last_green_splits = green_splits

        return WebsterPlan(
            tls_id=self._scene_meta.tls_id,
            cycle_length=C_new,
            green_splits=green_splits,
            yellow_times=self._fixed_yellow_times,
            timestamp=current_sim_time,
            reason=f"predicted_flow_change_{max_change*100:.0f}%",
        )

    def get_stats(self) -> AdapterStats:
        return self.stats

    def reset_stats(self) -> None:
        """重置统计字段,供 CAMaxPressureAlgorithm.reset() 调用。"""
        self.stats = AdapterStats(
            updates_total=0,
            updates_skipped_threshold=0,
            updates_skipped_interval=0,
            last_update_step=0,
            last_predicted_flows={},
            last_green_splits=[],
        )

    def get_base_cycle(self) -> float:
        return self._base_cycle

    def get_initial_splits(self) -> List[Tuple[int, float]]:
        return list(self._initial_green_splits)
```

### 5.3 `algorithms/ca_max_pressure.py`

```python
class CAMaxPressureAlgorithm(BaseControlAlgorithm):
    def __init__(
        self,
        cloud_policy: CloudPolicy,
        webster_adapter: WebsterAdapter,
    ):
        self.cloud_policy = cloud_policy
        self.adapter = webster_adapter
        self._current_cycle: float = 0.0
        self._current_splits: List[Tuple[int, float]] = []

    def init(self, scene: Scene) -> None:
        self.scene = scene
        # 通过 WebsterAdapter 暴露的公开 getter 取初值,
        # 不直接读私有属性(避免与未来重构耦合)。
        self._current_cycle = self.adapter.get_base_cycle()
        self._current_splits = self.adapter.get_initial_splits()

    def step(self, state: JointState) -> List[ControlAction]:
        # 1. 喂历史 + 取云端预测
        self.cloud_policy.push_state(state)
        pred = self.cloud_policy.predict(state)

        # 2. 喂 Webster 适配器
        plan = self.adapter.update(
            pred.predicted_flows,
            self._current_cycle,
            self._current_splits,
            current_sim_time=state.timestamp,
        )
        if plan is None:
            return []

        # 3. 写状态 + 输出 SUMO 控制动作
        self._current_cycle = plan.cycle_length
        self._current_splits = plan.green_splits
        return [
            ControlAction(
                tls_id=plan.tls_id,
                action_type="set_phase_duration",
                value=plan.green_splits,
                reason=plan.reason,
            )
        ]

    def reset(self) -> None:
        self._current_cycle = self.adapter.get_base_cycle()
        self._current_splits = self.adapter.get_initial_splits()
        self.adapter.reset_stats()

    @property
    def name(self) -> str:
        return "ca_maxpressure_webster"
```

### 5.4 错误处理

| 失败点 | 兜底策略 |
|---|---|
| `model.pkl` 不存在 | CloudPolicy 返回 `state.flows`,行为与原 skeleton 一致 |
| XGBoost 推理异常 | try/except,记 log,返回兜底 |
| Webster 公式 `Y ≥ 1` | `max(1 - Y, 0.01)` 钳位,防除零 |
| 计算周期 < cycle_min 或 > cycle_max | clip 到 [cycle_min, cycle_max] |
| `set_phase_duration` 写入 SUMO 失败 | TraciBridge 已有 try/except,本步跳过,下一周期重试 |
| 5 分钟内多次进入 update | 节奏检查直接返回 None,记 stats |

---

## 6. 评估

### 6.1 第一层:预测准确性(离线)

```
输入: ml/model.pkl + datasets/demo_1_test.csv (15 次仿真,独立留出)
输出:
  - RMSE_per_direction: Dict[str, float]  (4 个方向)
  - MAE_per_direction: Dict[str, float]
  - R²_overall: float
  - 预测值 vs 真实值散点图 (visualization/plots.py)
```

**合格线**: val R² ≥ 0.5;若 R² < 0.5 简化特征,只保留 (queue, flow, hour_sin/cos)。

### 6.2 第二层:端到端仿真对比(在线)

```
对 demo_1 × 3 流量级,各跑 5 次仿真 (5 随机种子):
  - baseline_fixed:    FixedTimeAlgorithm (固定配时)
  - baseline_webster:  经典 Webster (按 xlsx 配时,不接 ML)
  - experiment:        CAMaxPressureWebsterAlgorithm (本设计)

每组指标(取 5 次平均):
  - 平均延误 (s/veh)
  - 平均排队长度 (veh)
  - 平均行程时间 (s)
  - 停车次数 (次/veh)
  + 派生指标:
    - WebsterAdapter 更新次数 (从 AdapterStats)
    - 阈值/节奏跳过次数占比 (分析"为什么不更新")
    - 仿真期间周期变化范围 (max - min)

输出:
  - output/comparison_table.csv (行 = 流量级,列 = 指标 × 3 算法)
  - output/comparison_bar.png (按流量级 × 指标 × 算法的柱状图)
  - output/phase_timing_timeline.png (配时随时间变化曲线)
  - output/prediction_scatter.png (第一层散点图)
```

### 6.3 验收口径

方案 B "成功"的判据(用于 9.1 答辩):

1. **必达**: 实验组在平均延误 / 平均排队长度两个主指标上,**优于 baseline_fixed**;
2. **加分**: 实验组**接近 baseline_webster** (差距 < 10%),说明动态调参没把经典算法带崩;
3. **惊喜**: 实验组在 **3.0x 高峰流量** 下优于 baseline_webster,因为 Webster 在饱和时反而失效,
   ML 提前预判能改善。

---

## 7. 风险与缓解

| # | 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|---|
| 1 | `collector.csv` 缺 `flow_*` 字段 | 中 | 高 | **Day 1 验证**,缺则补 D 组 collector |
| 2 | XGBoost 样本不足 15 次仿真 | 低 | 中 | 必要时把 1.0x 跑 10 次 |
| 3 | Webster 动态震荡 | 高(已知) | 中 | EMA + 阈值 + 周期边界,4 道防抖 |
| 4 | 周期变化干扰方案 A 绿波 | 中 | 低(9.1 不实现 A) | 9.1 单路口跑,后续再处理 |
| 5 | XGBoost 过拟合,test R² 暴跌 | 中 | 中 | early stopping + val 监控;R²<0.5 退回简化特征 |
| 6 | CloudPolicy.predict() 每步调用拖慢仿真 | 中 | 低 | XGBoost 推理 < 1ms;但用 5 分钟节流避免每步 |
| 7 | `scene_meta` 缺 `sat_flow_per_lane` | 中 | 中 | 9.1 用统一经验值(直行 1800 veh/h/lane,左转 1600),后续按 xlsx 校准 |
| 8 | Webster 公式在 SUMO 默认 4 相位 + 黄灯 + 全红 上算不准 | 中 | 中 | 用 SUMO 实际损失时间校准 `total_lost_time_per_cycle`,而非理论 4s/相位 |

---

## 8. 9.1 验收清单

- [ ] `experiments/data_generator.py` 跑完 15 次仿真,产出 `datasets/demo_1_train.csv` 含 `flow_*` 字段
- [ ] `ml/train.py` 训练出 `ml/model.pkl`,val R² ≥ 0.5
- [ ] `cloud/cloud_policy.py` 真实推理路径走通(单测:给定状态 → 非兜底预测)
- [ ] `cloud/webster_adapter.py` 单元测试:节奏检查、阈值检查、EMA、周期边界、绿信比分配
- [ ] `algorithms/ca_max_pressure.py.step()` 接到 SUMO,demo_1 跑 3600 秒无崩溃
- [ ] 第二层评估产出 `output/comparison_table.csv` (9 行: 3 流量级 × 3 算法)
- [ ] 答辩材料:4 张图 + 1 张表 + 1 段 5 分钟讲稿

---

## 9. 显式不做(Out of Scope)

- 多路口批量适配 —— 9.1 只 demo_1
- 在线增量学习 —— 离线一次性训练
- 模型热加载/版本管理 —— 替换靠重启
- LSTM/Transformer 时序建模 —— XGBoost tabular
- DQN/PPO/MARL 强化学习 —— 不在本设计
- 模型可解释性 (SHAP) —— 时间紧,有需要再补
- 干线绿波协调(方案 A) —— 由独立 spec 覆盖
- 真实 MEC/RSU 边缘部署 —— 仅在报告"未来工作"提及

---

## 10. 后续阶段(9.1 → 9.15 衔接)

完成 9.1 验收清单后,9.1-9.15 还有 2 周:

1. 训练数据扩展到 5-10 路口,模型改为按路口分别训练(每路口一个 model.pkl)
2. WebsterAdapter 引入"上游-下游"耦合,支持方案 A 干线绿波
3. 写完整对比报告,整合方案 A(绿波) + 方案 B(ML 增强)
4. 准备 5-8 分钟 Demo 视频脚本

这些不在本 spec 范围,届时另起 spec。

---

## 附录 A:与 README/任务书的差异

| 现有说法 | 本设计 | 处理建议 |
|---|---|---|
| README:核心策略 = 固定配时 / 规则自适应 / ML 增强 | 本设计只实现 ML 增强,规则自适应未触动 | README 改动:方案 B 锁定为"ML 增强 Webster",不另起"规则自适应" |
| W1-A2 任务书:Webster 基线算法 | Webster 由 ca_maxpressure 复用,单独"基线 Webster" 用于对比 | A2 任务改为:实现 baseline_webster = 一次性按 xlsx 配时跑,不调参,作为对比组 |
| 180 次跑批 = 60 场景 × 3 算法 | 9.1 完成 demo_1 (3 流量级 × 3 算法 = 9 次),后续 9.1-9.15 完成剩余 19 路口 | 文档化阶段交付,不冲突 |

---

## 附录 B:参考资料

- **Libsignal**: an open library for traffic signal control. Springer 2023.
  https://link.springer.com/article/10.1007/s10994-023-06412-y
- **Webster 公式**: 最佳信号周期 C₀ = (1.5L + 5) / (1 - Y)
- **Pi-Star-Lab/RESCO**: 强化学习/经典信号控制 benchmark.
  https://github.com/Pi-Star-Lab/RESCO
- **LibSignal/LibSignal**: 多算法统一接口.
  https://github.com/LibSignal/LibSignal
- **case547/sumo-rl**: SUMO + RL 环境(state 设计可借鉴).
  https://github.com/case547/sumo-rl
- **1486402863/sumolights**: A1 任务书要 fork 的 MaxPressure + Webster + SOTL 集合.
  https://github.com/1486402863/sumolights
- **opendilab/DI-smartcross**: 工业级决策智能信号控制.
  https://github.com/opendilab/DI-smartcross

---

**审阅状态**: 待用户复审
**下一步**: 用户批准 → 调用 superpowers:writing-plans 写实施计划