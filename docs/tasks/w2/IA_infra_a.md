# W2 任务书：仿真基础设施 A（IA）

> 周期：7/27（周日）- 8/2（周六）
> 核心目标：确保 20 路口在新版 SUMO 下全部稳定运行；协助实验组准备批量运行环境

---

## 每日任务

### Day 1（7/27 周日）

1. 复查 W1 迁移结果：重新运行 `scripts/validate_all.py`
2. 对 W1 中标记为"有问题"的路口做最终修复
3. 确保 20/20 路口 `sumo -c demo_N.sumocfg --no-step-log -e 3600` 全部通过

### Day 2（7/28 周一）

1. 为每个路口的 sumocfg 补充必要输出配置（如果缺失）：
   - `<tripinfo-output value="tripinfo.xml"/>` — 行程信息（EX 采集用）
   - `<fcd-output value="traj.xml"/>` — 车辆轨迹（DB 时空轨迹图用）
   - `<summary-output value="stats.xml"/>` — 统计摘要
2. **注意**：不修改原始文件。在 `src/platform/configs/` 下生成增强版 sumocfg：
   ```
   src/platform/configs/demo_1.sumocfg  (引用原始 net.xml/rou.xml，增加输出配置)
   src/platform/configs/demo_2.sumocfg
   ...
   ```
3. 更新 main.py 使用增强版 sumocfg

### Day 3（7/29 周二）

1. 编写 `scripts/batch_validate.py`：
   - 对 20 路口各跑 3600 步（无 GUI）
   - 记录每个路口的：运行时间、完成车辆数、是否有报错
   - 输出汇总表
2. 运行脚本，确认 20 路口在 3600 步内都能正常完成
3. 记录每个路口的运行时间（估算 360 次实验总时间）

### Day 4（7/30 周三）

1. 协助 EX 调试 runner.py：
   - 确认 `--output-dir` 参数正确输出 tripinfo.xml/stats.xml/traj.xml
   - 确认 `--seed` 参数能改变随机种子（SUMO 的 `--seed` 选项）
   - 确认 `--flow-multiplier` 参数能正确放大流量
2. 在路口 1 上做一次完整的"模拟实验"：
   - 运行 runner.py 的单次实验函数
   - 验证输出文件完整

### Day 5（7/31 周四）

1. 补全 `metadata/intersections.yaml`（如果 W1 未完成）
2. 更新 `docs/edge_mapping.md`（如果 W1 有遗漏）
3. 编写 `docs/sumo_env_setup.md`：SUMO 环境安装指南（供部署文档使用）
   - Windows 安装步骤
   - 环境变量配置
   - 常见报错与解决

### Day 6（8/1 周五）

1. 协助 TL 做 W2 集成验证
2. 如果有多台机器可用，配置第二台机器的 SUMO 环境（为 W3 并行跑实验准备）
3. 提交所有代码给 TL

### Day 7（8/2 周六）

1. Buffer：修复本周发现的问题
2. 开始调研 Docker 中安装 SUMO 的方案（W4 任务前置）：
   - 搜索 `sumo docker image`
   - 确认是否有官方/社区 Docker 镜像
   - 记录基础镜像选择

---

## 交付物清单

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | 20 路口 3600 步全部通过 | 7/27 | batch_validate 输出 20/20 PASS |
| 2 | `src/platform/configs/` 增强版 sumocfg | 7/28 | 含 tripinfo/fcd/summary 输出 |
| 3 | `scripts/batch_validate.py` | 7/29 | 批量验证 + 运行时间统计 |
| 4 | `docs/sumo_env_setup.md` | 7/31 | 安装指南完整 |
| 5 | Docker 调研笔记 | 8/2 | 基础镜像确定 |
