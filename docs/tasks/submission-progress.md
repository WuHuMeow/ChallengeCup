# 提交收敛进度

> 最终截止：2026-09-01
> 执行模式：一人主导、AI 执行
> 当前阶段：质量基线冻结

## 阶段门禁

| 阶段 | 截止 | 状态 | 证据入口 |
|---|---|---|---|
| 质量基线 | 2026-08-02 | 已完成 | `output/evidence/baseline/` |
| Docker 与第二机器 | 2026-08-07 | Docker 完成 | `output/evidence/docker/`、`second-machine/` |
| 正式实验 | 2026-08-16 | **已完成** | `output/evidence/matrix-final/` (360/360, 0 fail) |
| 正式材料 | 2026-08-25 | 待开始 | `output/deliverables/` |
| 提交包 | 2026-08-31 | 待开始 | `output/submission/` |
| 统计分析 | 2026-08-03 | **已完成** | `output/evidence/statistics-final/` |

## 今日状态

| 日期 | 唯一主目标 | 结果 | 验证命令 | 下一步 |
|---|---|---|---|---|
| 2026-07-30 | 修复跨盘符缺陷，冻结绿色基线 | 通过 | `pytest tests -q` → 198 passed; compileall/flake8/git diff --check 全部通过 | 建立进度台账和证据目录契约 |
| 2026-07-30 | 本地 SUMO 快速验收 | 通过 | `verify_ia_ib.py --quick` → 退出码 0; 12 pass, 0 fail, 2 not_run (enhanced_3600/docker) | 提交基线证据；等待主导人安装 Docker 后执行 Task 4 |
| 2026-07-31 | 修复 subprocess 编码 + 实现统计分析脚本 | 通过 | 202 tests passed; flake8 clean; `analyze_matrix.py` 2 新测试通过 | 等待 Docker Desktop；运行预实验矩阵 (Task 6) |
| 2026-08-03 | **36000 步正式矩阵全量完成 + 统计分析** | 通过 | 360/360 completed, 0 fail; `analyze_matrix.py` 产出 final statistics; 200 tests | 报告/PPT/视频 |

## 主导人介入事项

| 最晚日期 | 操作 | 预计用时 | 完成证据 |
|---|---|---:|---|
| ~~2026-08-03~~ 2026-08-01 | 安装并启动 Docker Desktop | 已完成 | `docker version` 输出; `ca-mp:ia-ib` 镜像已构建 |
| 2026-08-06 | 提供第二台电脑 | 60–90 分钟 | `second-machine.json` |
| 2026-08-17 | 确认学校、团队、成员、指导教师和署名顺序 | 20 分钟 | 主导人书面确认 |
| 2026-08-24 | 录制真人讲解 | 60–120 分钟 | 原始音视频文件 |
| 2026-09-01 | 上传并确认比赛平台状态 | 30 分钟 | 平台成功截图 |
