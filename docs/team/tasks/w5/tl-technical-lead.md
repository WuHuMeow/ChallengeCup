# Tech Lead W5 任务书

> 周期：8/17–8/23 | 核心目标：交付物质量把控，报告/PPT/视频/演示方案初稿全部完成

## 每日任务

### Day 1（8/17）

- [ ] Review DA 的报告全文初稿：逻辑是否连贯、数据是否与实验 CSV 一致、是否覆盖赛题 PDF 所有要求
- [ ] 逐章核对数据：报告中引用的数字能否在 `output/csv/` 中找到对应来源
- [ ] 提出修改意见清单（按章节编号），发给 DA
- [ ] 确认报告覆盖了三个功能模块的描述

核对报告数据的方法：

```python
import pandas as pd

# 报告中若写"路口 16 CA-MP 平均排队 X 辆"，用此验证
df = pd.read_csv("output/csv/16_normal_ca_maxpressure_s42.csv")
print(f"路口16 CA-MP 平均排队: {df['avg_queue_length'].mean():.2f}")
print(f"路口16 CA-MP 平均延误: {df['avg_delay'].mean():.2f}")

# 多 seed 取均值（报告中应汇报 3 次均值）
dfs = [pd.read_csv(f"output/csv/16_normal_ca_maxpressure_s{s}.csv") for s in [42, 123, 456]]
means = [d["avg_queue_length"].mean() for d in dfs]
print(f"3 seed 均值: {sum(means)/3:.2f} ± {pd.Series(means).std():.2f}")
```

**验证：** 打开报告目录页，确认包含：项目概述、系统架构、算法设计、实验结果、部署说明 五大章节

### Day 2（8/18）

- [ ] Review PPT 初稿：19 页是否齐全、每页信息量是否合适、与报告内容是否一致
- [ ] 重点检查：算法对比页是否有数据支撑、架构图是否与代码结构一致
- [ ] 与 DA 协调修改，确认修改截止时间
- [ ] 确认 PPT 中无错别字和格式问题

核对 PPT 中架构图与代码结构的对应关系：

```
PPT 架构图应反映：
  cloud/cloud_policy.py  → 云端（EWMA 预测 + base_green 下发）
  algorithms/ca_max_pressure.py → 边缘（CA-MP 决策）
  engine/traci_bridge.py → 车端/路侧（执行 + 状态反馈）
  core/types.py → 数据契约（JointState / ControlAction / PredictionResult）
```

**验证：** PPT 页数 = 19，每页有标题，无空白页

### Day 3（8/19）

- [ ] 检查 DB 的视频录制进度：素材是否齐全
- [ ] 确认旁白文字稿是否就绪、时长是否在 5-8 分钟范围内
- [ ] 如素材不足，协调补录
- [ ] 确认视频分辨率 ≥ 1080p

视频素材清单核对：

```
必须包含的片段：
  □ 路口 16 三算法对比（SUMO-GUI 录屏或图表动画）
  □ 1.5 倍流量下 CA-MP vs FixedTime 对比
  □ 云-边-端数据流动画（JointState → CA-MP → ControlAction）
  □ 系统架构总览
  □ 实验结果汇总表/图
```

**验证：** 视频素材文件夹中有：路口 16 对比片段、1.5 倍流量对比片段、架构动画片段

### Day 4（8/20）

- [ ] Review 演示方案文档（DA 产出）：是否覆盖赛题要求的 4 项内容
- [ ] 确认路口 16 的描述准确（24m 短边、溢出门控触发）
- [ ] 提出修改意见
- [ ] 确认部署运行说明文档（IB 产出）是否完整

演示方案必须覆盖（对照赛题 PDF）：

```
  □ 场景描述：雄安"窄路密网"特征、路口 16 的 24m 短边
  □ 算法配置：如何启动 CA-MP、参数含义（overflow_threshold=0.9, base_green=30）
  □ 演示脚本/流程：从 docker build 到看到对比结果的完整步骤
  □ 关键演示材料：对比截图、数据表格
```

验证部署文档可执行：

```bash
# 按部署文档的步骤走一遍
docker build -t ca-mp .
docker run ca-mp python examples/run_fixed_time.py 1
# 应无报错
```

**验证：** 演示方案包含：场景描述、算法配置步骤、演示脚本、预期结果截图

### Day 5（8/21）

- [ ] 全员进度检查：DA 报告/PPT 定稿进度、DB 视频剪辑进度、其他组有无遗留 bug
- [ ] 确定 W6 最终打磨计划：谁改什么、截止时间
- [ ] 确认代码仓库 README 是否需要更新
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
- [ ] 确认提交方式和文件大小限制

W6 review 清单模板：

```
对照赛题 PDF 第八点，7 项提交材料：
  □ PPT 汇报 (.pptx) — DA
  □ 可运行仿真系统 + 源代码 — TL
  □ 部署运行说明文档 — IB
  □ 实验评估报告 (Word) — DA + EX
  □ 演示视频 5-8 分钟 (.mp4) — DB
  □ 实际场景演示方案 — DA
  □ Dockerfile + 部署文档 — IB
```

**验证：** review 清单包含赛题要求的 7 项提交材料，每项标注负责人和状态

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
