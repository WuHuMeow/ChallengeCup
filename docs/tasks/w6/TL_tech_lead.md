# Tech Lead W6 任务书

> 周期：8/24–8/31 | 核心目标：最终打磨、全员 review、打包提交

## 每日任务

### Day 1（8/24）

- [ ] 组织全员最终 review 会议：逐页过 PPT（15 分钟模拟答辩）、通读报告关键段落、观看视频最终版
- [ ] 收集所有人意见，整理为修改清单（按负责人分组）
- [ ] 确认修改清单中每项有明确负责人和截止时间
- [ ] 对照赛题 PDF 提交要求逐项检查完整性

修改清单格式：

```
[DA] 报告第 4 章实验数据表格格式不统一 — 8/26
[DB] 视频 3:20 处路口编号标错 — 8/26
[AB] ca_max_pressure.py 第 47 行注释与逻辑不符 — 8/26
[IA] Dockerfile 缺少 openpyxl 依赖 — 8/25
[EX] 路口 7 数据缺失需重跑 — 8/26
```

**验证：** 修改清单列出，每项格式为 `[负责人] 修改内容 — 截止日`

### Day 2（8/25）

- [ ] 分配修改任务给各组，设定统一截止时间 8/27
- [ ] 自己负责：README.md 最终版更新
- [ ] 确认 README 中的快速开始命令在当前代码下可执行
- [ ] 确认仓库根目录结构清晰、无冗余文件

README 快速开始验证：

```bash
# 按 README 中的步骤走一遍
python -c "import traci; print('traci', traci.__version__)"
python -c "import pandas, numpy; print('all dependencies OK')"
python examples/run_fixed_time.py 1
# 三步都应无报错
```

**验证：** `python examples/run_fixed_time.py 1` → 无报错（README 中的命令可复现）

### Day 3（8/26）

- [ ] 跟踪各组修改进度
- [ ] 确认仓库结构最终版：`.gitignore` 正确、无敏感文件、无大文件误提交
- [ ] 确认 `requirements.txt` 与实际依赖一致
- [ ] 检查所有 Python 文件无语法错误

仓库最终检查：

```bash
# 语法检查
python -m py_compile core/types.py algorithms/base.py algorithms/ca_max_pressure.py
python -m py_compile engine/runner.py experiments/runner.py cloud/cloud_policy.py
python -m py_compile scenes/registry.py scenes/variant.py

# 确认无敏感文件
git ls-files | grep -E "\.env|credential|secret|\.key"
# 应无输出

# 确认 .gitignore 生效
git status --short
# 应无 __pycache__、.pyc、output/ 等
```

**验证：** `python -m py_compile core/types.py algorithms/base.py algorithms/ca_max_pressure.py engine/runner.py experiments/runner.py` → 无报错

### Day 4（8/27）

- [ ] 所有修改完成，做最终集成验证
- [ ] 验证 1：本地仿真跑通
- [ ] 验证 2：Docker 内仿真跑通
- [ ] 确认报告/PPT/视频/演示方案文件完整且可打开
- [ ] 打 tag：`git tag v1.0-final`

最终集成验证：

```bash
# 本地验证
python examples/run_fixed_time.py 16
python -m pytest tests/ -v

# Docker 验证
docker build -t ca-mp .
docker run ca-mp python examples/run_fixed_time.py 1

# 仓库状态
git status   # 应为 clean
git tag -l   # 应包含 v0.1-w1-complete ~ v1.0-final
```

**验证：** `git tag -l "v1.0*"` → 输出 `v1.0-final`

### Day 5（8/28）

- [ ] 准备提交材料包（7 项）
- [ ] 确认比赛平台要求的提交格式和大小限制
- [ ] 压缩包命名：`学校全称-团队名称-车路云协同管控算法与平台-负责人姓名`
- [ ] 逐项检查材料包完整性

提交材料清单：

```
  □ 1. PPT 汇报 (.pptx)
  □ 2. 代码仓库 (zip 或 Git 链接)
  □ 3. 部署运行说明文档 (Markdown/PDF)
  □ 4. 实验评估报告 (Word + PDF)
  □ 5. 演示视频 (.mp4, 5-8 分钟)
  □ 6. 实际场景演示方案 (Word/Markdown)
  □ 7. Dockerfile + 部署文档
```

**验证：** 材料包内 7 项文件齐全，压缩包大小符合平台限制

### Day 6（8/29）

- [ ] 模拟答辩（全员）：一人主讲 PPT（12 分钟）、其他人扮演评委提问（5 分钟）
- [ ] 记录回答不好的问题，补充准备答案
- [ ] 确认答辩分工：谁讲哪部分、谁负责回答哪类问题
- [ ] 如时间允许，再模拟一轮

答辩分工模板：

```
主讲：DA（12 分钟 PPT）
  - 项目背景与需求（2 min）
  - 系统架构与云-边-端设计（3 min）
  - CA-MP 算法创新点（3 min）
  - 实验结果与对比分析（3 min）
  - 总结与展望（1 min）

问答分工：
  - 算法原理类 → AB
  - 仿真平台类 → IB
  - 实验设计类 → EX
  - 部署运维类 → IA
```

**验证：** 答辩分工表列出，每人知道自己负责的部分

### Day 7（8/30–8/31）

- [ ] 8/30 最终提交：上传所有材料到比赛平台，确认上传成功、文件可打开，截图保存提交确认
- [ ] 8/31 Buffer：如 8/30 提交有问题则修复重交；如已成功则全员休息
- [ ] 确认提交后仓库状态干净

最终提交检查：

```bash
# 确认仓库干净
git status  # 应为 "nothing to commit, working tree clean"

# 确认 tag 完整
git tag -l  # v0.1-w1-complete, v0.2-w2-complete, ..., v1.0-final

# 确认远程同步
git log --oneline origin/master..HEAD  # 应无输出（本地无未推送 commit）
```

**验证：** 比赛平台显示提交成功，截图已保存

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
