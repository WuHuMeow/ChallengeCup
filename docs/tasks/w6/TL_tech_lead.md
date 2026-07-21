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
