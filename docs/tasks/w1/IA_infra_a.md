# W1 任务书：仿真基础设施 A（IA）

> 周期：7/20（周日）- 7/26（周六）
> 核心目标：将 20 个路口全部迁移到统一 SUMO 版本，确保可运行

---

## 背景

主办方提供的 20 个路口使用了至少 5 个 SUMO 版本（1.13.0 / 1.18.0 / 1.23.1 / 1.26.0 / 1.27.1），步长分 1s 和 0.1s 两档。你需要将它们统一到新版 SUMO（建议 1.26.0 或 1.27.1），使所有路口能用同一套环境跑通。

---

## 每日任务

### Day 1（7/20 周日）

**环境搭建**
1. 安装 SUMO 最新版（推荐 1.27.1）：
   - Windows：从 https://sumo.dlr.de/docs/Downloads.html 下载安装包
   - 安装后设置环境变量：`SUMO_HOME=C:\Program Files\Eclipse\Sumo`（或你的安装路径）
2. 验证安装：`sumo --version` 输出版本号
3. 验证 Python 接口：`python -c "import traci; print(traci.__version__)"`
4. 用 SUMO-GUI 打开路口 1：`sumo-gui -c data/intersection_data/1/sumo工程/demo_1.sumocfg`
   - 如果能正常打开并运行 → 记录"路口 1 兼容"
   - 如果报错 → 记录错误信息，分析原因

**建立迁移记录表**
5. 在 `docs/` 下创建 `migration_log.md`，格式：

```markdown
| 路口 | 原始版本 | 步长 | 迁移状态 | 问题记录 |
|------|----------|------|----------|----------|
| 1    | 1.18.0   | 1s   | 待验证   |          |
| 2    | ?        | ?    | 待验证   |          |
| ...  |          |      |          |          |
```

### Day 2（7/21 周一）

**批量验证（不修改文件）**
1. 写一个 Python 脚本 `scripts/validate_all.py`：
   - 遍历 `data/intersection_data/1~20/sumo工程/demo_N.sumocfg`
   - 对每个路口执行 `sumo -c demo_N.sumocfg --no-step-log` 跑 100 步
   - 记录：成功/失败、错误信息、运行时间
2. 运行脚本，得到 20 个路口的兼容性报告
3. 更新 `migration_log.md`

**预期结果**：大部分路口应该能直接跑（SUMO 向后兼容性好），少数可能需要处理。

### Day 3（7/22 周二）

**处理不兼容路口**
1. 对于报错的路口，常见修复方法：
   - XML schema 变化：用 `netconvert -s old.net.xml -o new.net.xml` 重新生成
   - 缺少文件：检查 `.sumocfg` 引用的文件是否都存在
   - 版本特有参数：删除或替换已废弃的 XML 属性
2. **重要**：不修改 `data/intersection_data/` 原始文件！
   - 将修复后的文件输出到 `data/intersection_data/N/sumo工程/` 中覆盖（因为 README 说 1~20 只读）
   - 或者：如果需要修改，在 `engine/configs/` 下生成新的 `.sumocfg` 指向修复后的文件
   - **与 TL 确认**：是直接在原目录修复，还是另建目录
3. 每修复一个路口，立即验证能跑通

### Day 4（7/23 周三）

**步长差异处理**
1. 路口 1-10、14 步长为 1s；路口 11-13、15-20 步长为 0.1s
2. 不需要统一步长——算法按仿真步调用即可
3. 但需要在 `metadata/intersections.yaml` 中补全所有 20 个路口的信息：
   - `timestep_s`
   - `sumo_versions`（统一后的版本）
   - `flow_count`
   - `has_queues`
   - `edge_naming`（边命名规则）
4. 更新 `metadata/intersections.yaml`（目前只有 3 个路口的信息，补全剩余 17 个）

### Day 5（7/24 周四）

**边命名标准化文档**
1. 各路口边命名不统一：
   - 路口 1：E0/-E1/-E2/-E3
   - 路口 11：W_car/E_car/S_car/N_car
   - 路口 16：含 -E5（5 进口道）
2. 编写 `docs/edge_mapping.md`：记录每个路口的边 ID → 方向（东/西/南/北）映射
3. 这个映射表后续算法组会用到（计算压力时需要知道哪个边是哪个方向）
4. 格式建议：

```markdown
## 路口 1
| 边 ID | 方向 | 类型 | 车道数 | 长度(m) |
|--------|------|------|--------|---------|
| -E1    | 西进口 | 进口 | 2 | 76.92 |
| E1     | 东出口 | 出口 | 2 | 76.92 |
| -E2    | 南进口 | 进口 | 3 | 101.28 |
| ...    |      |      |        |         |
```

### Day 6（7/25 周五）

**全量验证 + 提交**
1. 再次运行 `scripts/validate_all.py`，确认 20/20 全部通过
2. 将迁移结果提交给 TL
3. 如果有路口仍然失败，记录原因并告知 TL（可能需要降级处理：跳过该路口或用原始版本单独跑）

### Day 7（7/26 周六）

**Buffer / 协助**
1. 协助 IB 调试 TraCIBridge（IB 需要调用你验证过的路口）
2. 如果 W1 任务提前完成，开始编写 `scripts/migrate.py`（自动化迁移脚本，供报告使用）

---

## 交付物清单

| # | 文件 | 截止日 | 验收标准 |
|---|------|--------|----------|
| 1 | SUMO 环境安装完成 | 7/20 | `sumo --version` 正常输出 |
| 2 | `docs/migration_log.md` | 7/21 | 20 路口迁移状态记录 |
| 3 | `scripts/validate_all.py` | 7/21 | 能批量验证 20 路口 |
| 4 | 20 路口全部可运行 | 7/25 | validate_all.py 输出 20/20 PASS |
| 5 | `metadata/intersections.yaml` 补全 | 7/23 | 20 路口信息完整 |
| 6 | `docs/edge_mapping.md` | 7/24 | 20 路口边-方向映射表 |

---

## 常用命令参考

```bash
# 验证单个路口（无 GUI，跑 100 步）
sumo -c data/intersection_data/1/sumo工程/demo_1.sumocfg --no-step-log -e 100

# 用 netconvert 重新生成路网（修复旧版本文件）
netconvert -s data/intersection_data/N/sumo工程/demo_N.net.xml -o data/intersection_data/N/sumo工程/demo_N.net.xml.new

# 查看 SUMO 版本
sumo --version

# 用 GUI 打开（调试用）
sumo-gui -c data/intersection_data/1/sumo工程/demo_1.sumocfg
```

---

## 注意事项

- **不修改原始数据**——如需修复，先与 TL 确认方案
- 优先保证路口 1、11、16 能跑（这三个是重点路口）
- 遇到 SUMO 版本兼容问题，先查 https://sumo.dlr.de/docs/ChangeLog.html
- 每天更新 migration_log.md，让 TL 掌握进度
