# 任务书统一标准 Implementation Plan

> **历史快照：** 本计划记录任务书迁移前的文件名和目录。旧 `docs/tasks/` 路径属于原始实施范围，不可作为当前命令；现行任务入口见 `docs/team/tasks/`。
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 TL 角色的 W1-W6 任务书改写为统一标准模板，作为其余 7 个角色的参考。

**Architecture:** 每个任务书按固定 6 段结构改写（标题元信息 → 本周背景 → 每日任务 → 关键代码指引 → 交付物 → 协作对接）。W1 精简（砍完整源码、半天拆分、行为约束），W2-W6 补充（加验证命令、代码片段、具体验收标准）。

**Tech Stack:** Markdown, Python (代码片段引用)

## Global Constraints

- 不改变任务内容和分工安排，只统一格式和详细度
- 代码片段必须与仓库实际代码一致（`core/types.py` 含 PredictionResult、TrafficLevel 等；`experiments/runner.py` 使用 `run_batch()` 函数而非 CLI 参数）
- 每天 3-5 个子任务 + 至少一条验证命令
- 代码片段 10-30 行，标注完整实现文件路径
- 验收标准可判定（具体命令、字段名、预期输出）

---

### Task 1: 改写 TL W1 任务书（精简）

**Files:**
- Modify: `docs/tasks/w1/TL_tech_lead.md`

**Interfaces:**
- Consumes: 设计文档 `docs/superpowers/specs/2026-07-21-task-docs-unified-standard-design.md` 中的模板结构
- Produces: 统一标准的 TL W1 模板，后续 W2-W6 和其他角色参照此格式

- [ ] **Step 1: 用以下完整内容替换 `docs/tasks/w1/TL_tech_lead.md`**

```markdown
# Tech Lead W1 任务书

> 周期：7/20–7/26 | 核心目标：冻结核心接口，路口 1 固定配时 + CA-MP 跑通 3600 步

## 本周背景

本项目采用云-边-端三层架构：云端（`cloud/cloud_policy.py`）做流量预测，边缘（`algorithms/`）做信号决策，车端/路侧（`engine/traci_bridge.py`）执行控制并反馈状态。三层通过 `core/types.py` 中的共享数据类（JointState、ControlAction、PredictionResult）交互。W1 的核心是把这些接口定死，让 8 个人能并行开发。

## 每日任务

### Day 1（7/20）

- [ ] 初始化仓库：创建 `.gitignore`（排除 `__pycache__/`、`*.pyc`、`.env`、`experiments/results/`、`.venv/`）
- [ ] 创建 `requirements.txt`（traci, sumolib, pandas, numpy, matplotlib, pyyaml, openpyxl）
- [ ] 编写 `core/types.py`：定义 SceneMeta、Scene、JointState、QueueState、ControlAction、PredictionResult、SimulationMetrics 数据类，全部带类型注解
- [ ] 编写 `algorithms/base.py`：BaseControlAlgorithm ABC，含 `init(scene)`、`step(state) -> List[ControlAction]`、`reset()`、`name` 四个抽象成员
- [ ] 首次 commit 并将接口文件通知全员

**验证：** `python -c "from core.types import JointState, ControlAction; from algorithms.base import BaseControlAlgorithm; print('接口导入成功')"` → 输出 `接口导入成功`

### Day 2（7/21）

- [ ] 编写 `engine/runner.py` 骨架：SimulationRunner 类，支持启动仿真 → 逐步调用算法 → 采集指标 → 关闭
- [ ] 编写 `engine/traci_bridge.py` 骨架：TraCIBridge 类，封装 `start()`、`get_state() -> JointState`、`apply_actions()`、`step()`、`close()`
- [ ] 确认 IA 已开始 SUMO 版本迁移、IB 已开始 TraCI 封装、AA/AB 已开始算法实现
- [ ] 解答各组对接口的疑问

**验证：** `python -c "from engine.runner import SimulationRunner; print('runner 导入成功')"` → 输出 `runner 导入成功`

### Day 3（7/22）

- [ ] Review IA 提交的迁移结果：抽查路口 1、11、16 能否被 SUMO 正常加载
- [ ] Review IB 提交的 TraCIBridge 初版：确认 `get_state()` 返回的 JointState 字段完整
- [ ] 如发现接口设计缺陷，今天内修改并通知全员（唯一修改窗口）
- [ ] 编写 `docs/interface.md`：每个数据类的字段含义和使用方式

**验证：** `python -c "from scenes.registry import SceneRegistry; r = SceneRegistry(); print(len(r.list_scenes()), '个路口已注册')"` → 输出 `20 个路口已注册`

### Day 4（7/23）

- [ ] 接口冻结：此后 `core/types.py` 和 `algorithms/base.py` 不再修改
- [ ] 集成 IB 的 TraCIBridge + AA 的 FixedTimeAlgorithm 到主分支
- [ ] 在路口 1 上运行固定配时仿真 3600 步
- [ ] 确认输出 CSV 包含 avg_queue_length、avg_delay、total_throughput 列

**验证：** `python examples/run_fixed_time.py 1` → 无报错，`output/csv/` 下生成 CSV 文件

### Day 5（7/24）

- [ ] 集成 AB 的 CAMaxPressureAlgorithm
- [ ] 在路口 1 上运行 CA-MP 仿真 3600 步
- [ ] 对比两次运行的输出 CSV，确认 CA-MP 有输出差异（至少 avg_queue_length 不同）
- [ ] 如有集成冲突，协调 AB 修复

**验证：** `python examples/run_demo.py 1` → 两种算法均跑通，输出两个不同的 CSV

### Day 6（7/25）

- [ ] 合入 EX 的实验配置框架（`experiments/runner.py`）
- [ ] 合入 DA 的报告模板
- [ ] 检查全员代码能否无冲突合入主分支
- [ ] 编写 W1 周报：完成了什么、下周计划、风险点

**验证：** `git log --oneline -10` → 所有组员的 commit 已在主分支

### Day 7（7/26）

- [ ] 最终集成测试：路口 1 上固定配时和 CA-MP 都能跑通 3600 步
- [ ] 打 tag：`git tag v0.1-w1-complete`
- [ ] 确认 W2 各组任务无阻塞（experiments/runner.py 能调用三种算法）

**验证：** `git tag -l "v0.1*"` → 输出 `v0.1-w1-complete`

## 关键代码指引

```python
# 核心数据契约（完整实现见 core/types.py）
@dataclass
class JointState:
    step: int
    timestamp: float
    tls_id: str
    current_phase: int
    current_phase_name: str
    elapsed_phase_time: float
    queues: List[QueueState]
    flows: Dict[str, float]
    detector_values: Dict[str, float] = field(default_factory=dict)

@dataclass
class ControlAction:
    tls_id: str
    action_type: str  # "set_phase" / "set_phase_duration" / "set_program"
    value: Any
    reason: str = ""
```

```python
# 算法标准接口（完整实现见 algorithms/base.py）
class BaseControlAlgorithm(ABC):
    @abstractmethod
    def init(self, scene: Scene) -> None: ...
    @abstractmethod
    def step(self, state: JointState) -> List[ControlAction]: ...
    @abstractmethod
    def reset(self) -> None: ...
    @property
    @abstractmethod
    def name(self) -> str: ...
```

## 交付物

| 文件 | 截止 | 验收标准 |
|------|------|----------|
| `core/types.py` | Day 1 | 包含 SceneMeta、Scene、JointState、QueueState、ControlAction、PredictionResult、SimulationMetrics，全部有类型注解，`python -c "from core.types import *"` 无报错 |
| `algorithms/base.py` | Day 1 | BaseControlAlgorithm ABC 含 init/step/reset/name，`python -c "from algorithms.base import BaseControlAlgorithm"` 无报错 |
| `engine/runner.py` | Day 2 | SimulationRunner 类可实例化，`run(steps)` 方法签名存在 |
| `docs/interface.md` | Day 3 | 每个数据类字段有中文说明 |
| 集成验证 | Day 5 | 路口 1 两种算法跑通 3600 步，输出 CSV 有数据 |

## 协作对接

- Day 1 将 `core/types.py` 和 `algorithms/base.py` 发给全员，通知接口冻结时间（7/23）
- Day 2-3 与 IA/IB/AA/AB 确认各自开发无阻塞
- Day 6 收集全员代码合入主分支
```

- [ ] **Step 2: 验证文件格式**

Run: `head -5 docs/team/tasks/w1/tl-technical-lead.md`
Expected: 第一行为 `# Tech Lead W1 任务书`，第三行以 `> 周期：7/20–7/26` 开头

- [ ] **Step 3: Commit**

```bash
git add docs/team/tasks/w1/tl-technical-lead.md
git commit -m "docs: rewrite TL W1 task doc to unified standard"
```

---

### Task 2: 改写 TL W2 任务书（补充）

**Files:**
- Modify: `docs/tasks/w2/TL_tech_lead.md`

**Interfaces:**
- Consumes: Task 1 产出的 W1 模板格式
- Produces: 统一标准的 TL W2

- [ ] **Step 1: 用以下完整内容替换 `docs/tasks/w2/TL_tech_lead.md`**

```markdown
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

**验证：** `python -m pytest tests/unit/test_algorithms.py tests/unit/test_cloud.py -v` → 全部 passed

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
def run_batch(
    intersection_ids: List[str] | None = None,  # 默认全部 20 个
    algorithms: List[str] | None = None,         # 默认三种
    levels: List[TrafficLevel] | None = None,    # 默认 [NORMAL, HIGH]
    seeds: List[int] | None = None,              # 默认 [42, 123, 456]
    steps: int = 3600,
    output_root: Path | None = None,
) -> List[Dict[str, str]]:
    ...
```

```python
# EWMA 预测核心逻辑（完整实现见 cloud/cloud_policy.py）
def predict(self, state: JointState) -> PredictionResult:
    predicted = {}
    for direction, observed in state.flows.items():
        prev = self._prev_predicted.get(direction, observed)
        predicted[direction] = self.alpha * observed + (1 - self.alpha) * prev
    self._prev_predicted = predicted
    return PredictionResult(horizon_steps=self.horizon, ...)
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
```

- [ ] **Step 2: 验证文件格式**

Run: `head -5 docs/team/tasks/w2/tl-technical-lead.md`
Expected: 第一行为 `# Tech Lead W2 任务书`，第三行以 `> 周期：7/27–8/2` 开头

- [ ] **Step 3: Commit**

```bash
git add docs/team/tasks/w2/tl-technical-lead.md
git commit -m "docs: rewrite TL W2 task doc to unified standard"
```

---

### Task 3: 改写 TL W3 任务书（补充）

**Files:**
- Modify: `docs/tasks/w3/TL_tech_lead.md`

**Interfaces:**
- Consumes: Task 1-2 确立的模板格式
- Produces: 统一标准的 TL W3

- [ ] **Step 1: 用以下完整内容替换 `docs/tasks/w3/TL_tech_lead.md`**

```markdown
# Tech Lead W3 任务书

> 周期：8/3–8/9 | 核心目标：全量实验顺利运行，180 组原始流量实验完成，数据质量确认

## 每日任务

### Day 1（8/3）

- [ ] 确认 W2 预跑结果（路口 1-10 原始流量）无异常数据
- [ ] 启动路口 11-20 × 3 算法 × 原始流量 × 3 种子 = 90 组实验
- [ ] 监控运行状态，处理失败实验（记录失败路口和原因）
- [ ] 确认输出 CSV 目录结构正确：`output/csv/{路口}_{level}_{算法}_s{seed}.csv`

**验证：** `ls output/csv/ | wc -l` → 文件数持续增长（目标 180 个）

### Day 2（8/4）

- [ ] 检查实验进度：目标完成 180/360 组（原始流量部分）
- [ ] Review DB 产出的图表质量：配色是否统一、坐标轴标注是否清晰、分辨率 ≥ 300dpi
- [ ] Review DA 的报告初稿（第一/二/三章），提出修改意见
- [ ] 将修改意见整理为清单发给 DA 和 DB

**验证：** `ls output/csv/ | grep "normal" | wc -l` → ≥ 90（原始流量已完成过半）

### Day 3（8/5）

- [ ] 继续监控实验运行，处理失败实验
- [ ] 抽查 3-5 个路口的实验结果：CA-MP 的 avg_queue_length 是否低于 FixedTime
- [ ] 如某路口 CA-MP 效果不佳，与 AB 分析原因（可能是参数不适配或路口结构特殊）
- [ ] 记录异常路口编号和初步原因

**验证：** 随机抽取一个 CSV，`python -c "import pandas as pd; df = pd.read_csv('output/csv/5_normal_ca_maxpressure_s42.csv'); print(df['avg_queue_length'].mean())"` → 输出合理数值（非 NaN、非 0）

### Day 4（8/6）

- [ ] 确认原始流量 180 组实验全部完成（20 路口 × 3 算法 × 3 种子）
- [ ] 用 `experiments/metrics.py` 汇总全部结果
- [ ] 生成汇总对比表：20 路口 × 6 指标 × 3 算法
- [ ] 将完整数据发给 DA（报告）和 DB（图表）

**验证：** `ls output/csv/ | grep "normal" | wc -l` → 输出 `180`

### Day 5（8/7）

- [ ] Review 全部实验数据：CA-MP 优于 FixedTime 的路口比例（目标 > 80%）
- [ ] 标记异常路口（CA-MP 反而更差的），与 AB 讨论原因
- [ ] 确认数据质量：无缺失文件、无全零 CSV、无异常值
- [ ] 将异常分析结论记录到文档

**验证：** `python -c "import os; files = [f for f in os.listdir('output/csv') if 'normal' in f]; empty = [f for f in files if os.path.getsize(f'output/csv/{f}') < 100]; print(len(empty), '个异常文件')"` → 输出 `0 个异常文件`

### Day 6（8/8）

- [ ] 打 tag：`git tag v0.3-w3-complete`
- [ ] 编写 W3 周报
- [ ] 确认 W4 计划：1.5 倍压力测试 + EWMA 接入验证 + Docker 打包
- [ ] 与 IA 协调 Docker 环境准备

**验证：** `git tag -l "v0.3*"` → 输出 `v0.3-w3-complete`

### Day 7（8/9）

- [ ] 处理遗留问题（失败实验重跑、数据修补）
- [ ] 准备 W4 的 Docker 环境（确认 IA 已安装 Docker、基础镜像可用）
- [ ] 确认 DA/DB 已收到全部数据并开始制作

**验证：** `docker --version` → 输出版本号（确认环境就绪）

## 关键代码指引

```python
# 批量实验调用方式（完整实现见 experiments/runner.py）
from experiments.runner import run_batch
from core.types import TrafficLevel

# 原始流量全量跑批
results = run_batch(
    levels=[TrafficLevel.NORMAL],
    steps=3600,
)
# results 为 List[Dict]，每项含 intersection_id, algorithm, seed, csv 路径
```

## 交付物

| 文件 | 截止 | 验收标准 |
|------|------|----------|
| 原始流量 180 组 CSV | Day 4 | `output/csv/` 下 180 个文件，每个 > 100 字节 |
| 汇总对比表 | Day 4 | 20 路口 × 6 指标 × 3 算法，无空值 |
| 数据质量确认 | Day 5 | 无缺失、无全零、异常路口已标记 |
| git tag v0.3 | Day 6 | `git tag -l "v0.3*"` 有输出 |

## 协作对接

- Day 4 将完整实验数据发给 DA 和 DB
- Day 5 将异常路口分析发给 AB
- Day 6 与 IA 确认 Docker 环境就绪
```

- [ ] **Step 2: 验证文件格式**

Run: `head -5 docs/team/tasks/w3/tl-technical-lead.md`
Expected: 第一行为 `# Tech Lead W3 任务书`，第三行以 `> 周期：8/3–8/9` 开头

- [ ] **Step 3: Commit**

```bash
git add docs/team/tasks/w3/tl-technical-lead.md
git commit -m "docs: rewrite TL W3 task doc to unified standard"
```

---

### Task 4: 改写 TL W4 任务书（补充）

**Files:**
- Modify: `docs/tasks/w4/TL_tech_lead.md`

**Interfaces:**
- Consumes: Task 1-3 确立的模板格式
- Produces: 统一标准的 TL W4

- [ ] **Step 1: 用以下完整内容替换 `docs/tasks/w4/TL_tech_lead.md`**

```markdown
# Tech Lead W4 任务书

> 周期：8/10–8/16 | 核心目标：1.5 倍压力测试完成，EWMA 接入验证，Docker 打包可复现

## 本周背景

本周首次涉及 Docker 容器化：将 SUMO + Python 环境打包为镜像，使评审方无需安装任何依赖即可复现实验。Dockerfile 由 IA 编写，你负责验证容器内运行结果与本地一致。另外本周接入 EWMA 预测到 CA-MP 决策链路，验证预测是否带来额外收益。

## 每日任务

### Day 1（8/10）

- [ ] 启动 1.5 倍压力测试：`run_batch(levels=[TrafficLevel.HIGH], steps=3600)`，共 180 组
- [ ] 确认 `VariantGenerator` 正确生成 1.5 倍流量文件（检查 `output/variants/` 目录）
- [ ] 监控运行状态，处理失败实验
- [ ] 确认 1.5 倍流量下 CSV 的 avg_queue_length 明显高于原始流量（否则流量倍率未生效）

**验证：** `python -c "from scenes.variant import VariantGenerator; print('VariantGenerator 可用')"` → 输出 `VariantGenerator 可用`

### Day 2（8/11）

- [ ] Review AB 的 EWMA 预测实现：确认 `CloudPolicy.predict()` 每步被调用、`_prev_predicted` 状态正确更新
- [ ] 在路口 1 上对比：有 EWMA vs 无 EWMA 的 CA-MP 表现（avg_travel_time）
- [ ] 如 EWMA 效果不明显或引入 bug，与 AB 讨论是否保留
- [ ] 记录结论到文档

**验证：** `python -m pytest tests/unit/test_cloud.py -v` → 全部 passed

### Day 3（8/12）

- [ ] 检查 1.5 倍压力测试进度（目标完成过半）
- [ ] Review IA 的 Dockerfile：确认基于 `ubuntu:22.04`、安装了 SUMO 和 Python 依赖
- [ ] 构建镜像：`docker build -t ca-mp .`
- [ ] 容器内运行路口 1：`docker run ca-mp python examples/run_fixed_time.py 1`

**验证：** `docker run ca-mp python -c "import traci; print('容器内 traci 可用')"` → 输出 `容器内 traci 可用`

### Day 4（8/13）

- [ ] 确认 1.5 倍压力测试 180 组全部完成
- [ ] 用 `experiments/metrics.py` 采集结果
- [ ] 对比：原始流量 vs 1.5 倍流量下 CA-MP 相对 FixedTime 的优势是否更明显
- [ ] 将数据发给 DA 和 DB

**验证：** `ls output/csv/ | grep "high" | wc -l` → 输出 `180`

### Day 5（8/14）

- [ ] Review 全部代码质量：无未处理异常、无硬编码路径、关键函数有 docstring
- [ ] 确认 Docker 内运行结果与本地一致（同一路口同一算法的 avg_queue_length 差异 < 1%）
- [ ] 修复发现的问题
- [ ] 确认 `config/default.yaml` 中所有路径为相对路径

**验证：** `grep -r "C:\\\\" --include="*.py" . | grep -v __pycache__` → 无输出（无硬编码 Windows 路径）

### Day 6（8/15）

- [ ] 打 tag：`git tag v0.4-w4-complete`
- [ ] 编写 W4 周报
- [ ] 确认 W5 前置条件：所有实验数据齐全（原始 180 + 高压 180）、图表已生成、Docker 可复现
- [ ] 与 DA/DB 确认 W5 交付物制作计划

**验证：** `git tag -l "v0.4*"` → 输出 `v0.4-w4-complete`

### Day 7（8/16）

- [ ] 处理遗留问题
- [ ] 如 DB 的 PyQt 看板完成，做最终验证（能加载 CSV、显示对比曲线）
- [ ] 全员会议：确认 W5 分工和时间节点

**验证：** `ls output/csv/ | wc -l` → 输出 `360`（全量实验完成）

## 关键代码指引

```python
# 1.5 倍流量跑批（完整实现见 experiments/runner.py + scenes/variant.py）
from experiments.runner import run_batch
from core.types import TrafficLevel

results = run_batch(
    levels=[TrafficLevel.HIGH],  # 触发 VariantGenerator 生成 1.5x 流量文件
    steps=3600,
)
```

```python
# EWMA 预测接入点（完整实现见 cloud/cloud_policy.py）
class CloudPolicy:
    def predict(self, state: JointState) -> PredictionResult:
        # predicted(t+1) = α × observed(t) + (1-α) × predicted(t)
        ...
    def dispatch_base_green(self, state: JointState) -> float:
        # 云端周期性下发 base_green
        ...
```

## 交付物

| 文件 | 截止 | 验收标准 |
|------|------|----------|
| 1.5 倍压力测试 180 组 CSV | Day 4 | `output/csv/` 下含 "high" 的文件 180 个 |
| EWMA 接入验证结论 | Day 2 | 文档记录：效果提升/持平/退化的数据对比 |
| Docker 镜像 | Day 3 | `docker run ca-mp python examples/run_fixed_time.py 1` 无报错 |
| git tag v0.4 | Day 6 | `git tag -l "v0.4*"` 有输出 |

## 协作对接

- Day 2 将 EWMA 验证结论发给 AB
- Day 3 与 IA 确认 Dockerfile 和镜像构建
- Day 4 将高压实验数据发给 DA 和 DB
```

- [ ] **Step 2: 验证文件格式**

Run: `head -5 docs/team/tasks/w4/tl-technical-lead.md`
Expected: 第一行为 `# Tech Lead W4 任务书`，第三行以 `> 周期：8/10–8/16` 开头

- [ ] **Step 3: Commit**

```bash
git add docs/team/tasks/w4/tl-technical-lead.md
git commit -m "docs: rewrite TL W4 task doc to unified standard"
```

---

### Task 5: 改写 TL W5 任务书（补充）

**Files:**
- Modify: `docs/tasks/w5/TL_tech_lead.md`

**Interfaces:**
- Consumes: Task 1-4 确立的模板格式
- Produces: 统一标准的 TL W5

- [ ] **Step 1: 用以下完整内容替换 `docs/tasks/w5/TL_tech_lead.md`**

```markdown
# Tech Lead W5 任务书

> 周期：8/17–8/23 | 核心目标：交付物质量把控，报告/PPT/视频/演示方案初稿全部完成

## 每日任务

### Day 1（8/17）

- [ ] Review DA 的报告全文初稿：逻辑是否连贯、数据是否与实验 CSV 一致、是否覆盖赛题 PDF 所有要求
- [ ] 逐章核对数据：报告中引用的数字能否在 `output/csv/` 中找到对应来源
- [ ] 提出修改意见清单（按章节编号），发给 DA
- [ ] 确认报告覆盖了三个功能模块的描述

**验证：** 打开报告目录页，确认包含：项目概述、系统架构、算法设计、实验结果、部署说明 五大章节

### Day 2（8/18）

- [ ] Review PPT 初稿：19 页是否齐全、每页信息量是否合适、与报告内容是否一致
- [ ] 重点检查：算法对比页是否有数据支撑、架构图是否与代码结构一致
- [ ] 与 DA 协调修改，确认修改截止时间
- [ ] 确认 PPT 中无错别字和格式问题

**验证：** PPT 页数 = 19，每页有标题，无空白页

### Day 3（8/19）

- [ ] 检查 DB 的视频录制进度：素材是否齐全（路口 16 对比、高压力对比、云-边-端动画）
- [ ] 确认旁白文字稿是否就绪、时长是否在 5-8 分钟范围内
- [ ] 如素材不足，协调补录（确认哪些路口/场景需要补拍）
- [ ] 确认视频分辨率 ≥ 1080p

**验证：** 视频素材文件夹中有：路口 16 对比片段、1.5 倍流量对比片段、架构动画片段

### Day 4（8/20）

- [ ] Review 演示方案文档（DA 产出）：是否覆盖赛题要求的"场景描述、算法配置、演示脚本/流程、关键演示材料"
- [ ] 确认路口 16 的描述准确（24m 短边、溢出门控触发）
- [ ] 提出修改意见
- [ ] 确认部署运行说明文档（IB 产出）是否完整

**验证：** 演示方案包含：场景描述、算法配置步骤、演示脚本、预期结果截图

### Day 5（8/21）

- [ ] 全员进度检查：DA 报告/PPT 定稿进度、DB 视频剪辑进度、其他组有无遗留 bug
- [ ] 确定 W6 最终打磨计划：谁改什么、截止时间
- [ ] 确认代码仓库 README 是否需要更新（反映最终状态）
- [ ] 列出 W6 需要修复的所有 Issue

**验证：** 全员回复确认各自 W6 任务和时间节点

### Day 6（8/22）

- [ ] 打 tag：`git tag v0.5-w5-complete`
- [ ] 编写 W5 周报
- [ ] 确认所有交付物初稿完成：报告、PPT、视频初剪、演示方案、代码仓库、部署文档
- [ ] 将初稿清单发给全员确认

**验证：** `git tag -l "v0.5*"` → 输出 `v0.5-w5-complete`

### Day 7（8/23）

- [ ] 处理遗留问题
- [ ] 准备 W6 最终 review 清单（逐项对照赛题 PDF 提交要求）
- [ ] 确认提交方式（比赛平台上传/邮件/Git 仓库链接）和文件大小限制

**验证：** review 清单包含赛题要求的 7 项提交材料，每项标注负责人和状态

## 关键代码指引

本周以文档和交付物为主，无新代码。如需验证实验数据：

```python
# 读取实验结果（用于核对报告数据）
import pandas as pd
df = pd.read_csv("output/csv/16_normal_ca_maxpressure_s42.csv")
print(df[["avg_queue_length", "avg_delay", "total_throughput"]].mean())
```

## 交付物

| 文件 | 截止 | 验收标准 |
|------|------|----------|
| 报告 review 意见 | Day 1 | 按章节编号的修改清单已发给 DA |
| PPT review 意见 | Day 2 | 修改清单已发，19 页齐全 |
| 视频进度确认 | Day 3 | 素材齐全，时长 5-8 分钟 |
| 演示方案 review | Day 4 | 覆盖赛题 4 项要求 |
| git tag v0.5 | Day 6 | 所有初稿完成 |

## 协作对接

- Day 1-2 将 review 意见发给 DA
- Day 3 与 DB 确认视频素材和补录需求
- Day 5 全员确认 W6 分工
```

- [ ] **Step 2: 验证文件格式**

Run: `head -5 docs/team/tasks/w5/tl-technical-lead.md`
Expected: 第一行为 `# Tech Lead W5 任务书`，第三行以 `> 周期：8/17–8/23` 开头

- [ ] **Step 3: Commit**

```bash
git add docs/team/tasks/w5/tl-technical-lead.md
git commit -m "docs: rewrite TL W5 task doc to unified standard"
```

---

### Task 6: 改写 TL W6 任务书（补充）

**Files:**
- Modify: `docs/tasks/w6/TL_tech_lead.md`

**Interfaces:**
- Consumes: Task 1-5 确立的模板格式
- Produces: 统一标准的 TL W6（最终模板）

- [ ] **Step 1: 用以下完整内容替换 `docs/tasks/w6/TL_tech_lead.md`**

```markdown
# Tech Lead W6 任务书

> 周期：8/24–8/31 | 核心目标：最终打磨、全员 review、打包提交

## 每日任务

### Day 1（8/24）

- [ ] 组织全员最终 review 会议：逐页过 PPT（15 分钟模拟答辩）、通读报告关键段落、观看视频最终版
- [ ] 收集所有人意见，整理为修改清单（按负责人分组）
- [ ] 确认修改清单中每项有明确负责人和截止时间
- [ ] 对照赛题 PDF 提交要求逐项检查完整性

**验证：** 修改清单列出，每项格式为 `[负责人] 修改内容 — 截止日`

### Day 2（8/25）

- [ ] 分配修改任务：DA 报告/PPT 文字、DB 视频微调、AB/AA 代码 bug fix、IA/IB 部署文档、EX 数据核对
- [ ] 设定统一截止时间：8/27 所有修改完成
- [ ] 自己负责：README.md 最终版更新（反映最终项目状态和运行方式）
- [ ] 确认 README 中的快速开始命令在当前代码下可执行

**验证：** `python examples/run_fixed_time.py 1` → 无报错（README 中的命令可复现）

### Day 3（8/26）

- [ ] 跟踪各组修改进度
- [ ] 确认仓库结构最终版：`.gitignore` 正确、无敏感文件（`.env`、密钥）、无大文件误提交
- [ ] 确认 `requirements.txt` 与实际依赖一致
- [ ] 检查所有 Python 文件无语法错误

**验证：** `python -m py_compile core/types.py algorithms/base.py algorithms/ca_max_pressure.py engine/runner.py experiments/runner.py` → 无报错

### Day 4（8/27）

- [ ] 所有修改完成，做最终集成验证
- [ ] 验证 1：`python examples/run_fixed_time.py 16` 跑通
- [ ] 验证 2：`docker build -t ca-mp . && docker run ca-mp python examples/run_fixed_time.py 1` 跑通
- [ ] 确认报告/PPT/视频/演示方案文件完整且可打开
- [ ] 打 tag：`git tag v1.0-final`

**验证：** `git tag -l "v1.0*"` → 输出 `v1.0-final`

### Day 5（8/28）

- [ ] 准备提交材料包：代码仓库（zip 或 Git 链接）、报告 PDF+Word、PPT、视频 MP4、演示方案、部署文档
- [ ] 确认比赛平台要求的提交格式和大小限制
- [ ] 压缩包命名：`学校全称-团队名称-车路云协同管控算法与平台-负责人姓名`
- [ ] 逐项检查材料包完整性（7 项）

**验证：** 材料包内 7 项文件齐全，压缩包大小符合平台限制

### Day 6（8/29）

- [ ] 模拟答辩（全员）：一人主讲 PPT（12 分钟）、其他人扮演评委提问（5 分钟）
- [ ] 记录回答不好的问题，补充准备答案
- [ ] 确认答辩分工：谁讲哪部分、谁负责回答哪类问题
- [ ] 如时间允许，再模拟一轮

**验证：** 答辩分工表列出，每人知道自己负责的部分

### Day 7（8/30–8/31）

- [ ] 8/30 最终提交：上传所有材料到比赛平台，确认上传成功、文件可打开，截图保存提交确认
- [ ] 8/31 Buffer：如 8/30 提交有问题则修复重交；如已成功则全员休息
- [ ] 确认提交后仓库状态干净（`git status` 无未提交修改）

**验证：** 比赛平台显示提交成功，截图已保存

## 关键代码指引

本周无新代码。最终验证命令汇总：

```bash
# 本地验证
python examples/run_fixed_time.py 16
python -m pytest tests/ -v

# Docker 验证
docker build -t ca-mp .
docker run ca-mp python examples/run_fixed_time.py 1

# 仓库状态
git status  # 应为 clean
git tag -l  # 应包含 v0.1 ~ v1.0-final
```

## 交付物

| 文件 | 截止 | 验收标准 |
|------|------|----------|
| 全员 review 修改清单 | Day 1 | 每项有负责人和截止日 |
| 所有修改完成 | Day 4 | 无遗留 Issue |
| git tag v1.0-final | Day 4 | 最终代码+数据 |
| 提交材料包（7 项） | Day 5 | 齐全、可打开、命名正确 |
| 模拟答辩 | Day 6 | 全员参与，分工明确 |
| 最终提交 | Day 7 | 平台确认成功 |

## 协作对接

- Day 1 全员 review 会议
- Day 2 分配修改任务给各组
- Day 6 全员模拟答辩
```

- [ ] **Step 2: 验证文件格式**

Run: `head -5 docs/team/tasks/w6/tl-technical-lead.md`
Expected: 第一行为 `# Tech Lead W6 任务书`，第三行以 `> 周期：8/24–8/31` 开头

- [ ] **Step 3: Commit**

```bash
git add docs/team/tasks/w6/tl-technical-lead.md
git commit -m "docs: rewrite TL W6 task doc to unified standard"
```

---

### Task 7: 最终验证

**Files:**
- Verify: `docs/tasks/w1/TL_tech_lead.md` ~ `docs/tasks/w6/TL_tech_lead.md`

- [ ] **Step 1: 检查 6 个文件结构一致性**

Run:
```bash
for i in 1 2 3 4 5 6; do echo "=== W$i ==="; grep "^## " docs/team/tasks/w$i/tl-technical-lead.md; done
```

Expected: 每个文件都包含以下段落（顺序一致）：
- `## 本周背景`（W3/W5/W6 可省略）
- `## 每日任务`
- `## 关键代码指引`
- `## 交付物`
- `## 协作对接`

- [ ] **Step 2: 检查每天都有验证命令**

Run:
```bash
for i in 1 2 3 4 5 6; do echo "W$i:"; grep -c "验证" docs/team/tasks/w$i/tl-technical-lead.md; done
```

Expected: 每个文件 ≥ 7（每天至少一条）

- [ ] **Step 3: 确认无完整源码残留**

Run:
```bash
for i in 1 2 3 4 5 6; do lines=$(wc -l < docs/team/tasks/w$i/tl-technical-lead.md); echo "W$i: $lines lines"; done
```

Expected: 每个文件 80-150 行（W1 原文 237 行应大幅缩短，W2-W6 原文 54-83 行应适当增长）

- [ ] **Step 4: Final commit**

```bash
git add docs/team/tasks/
git commit -m "docs: TL W1-W6 task docs rewritten to unified standard (template)"
```
