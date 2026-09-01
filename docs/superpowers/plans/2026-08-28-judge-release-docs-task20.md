# Task 20 计划：评委向发布文档与陈旧声明边界

父计划：`docs/superpowers/plans/2026-08-18-judge-facing-final-release.md` Task 20。
前置：Task 19.D `9255a59`、19.E（本计划启动时其实现提交哈希见台账）。
本计划提交时 `docs/tasks/` 的任务文档保持原样；公开文档边界由检查器强制。

## 目标

把根 README 与部署/输出文档替换为评委可执行口径：以 canonical 算法 ID、
秒数窗口、540-run 形式矩阵与真实证据状态为准；删除内部分工表、旧
`actuated`/`1.5` 矩阵口径、历史"已完成"断言；新增 `docs/release/` 四份
评委文档与 `scripts/release/check_docs.py` 陈旧声明检查器，并用
`tests/test_release_docs.py` 锁定。

## 文件清单

- Create: `docs/release/README.md`
- Create: `docs/release/experiment-protocol.md`
- Create: `docs/release/evidence-contract.md`
- Create: `docs/release/algorithm-extension.md`
- Create: `scripts/release/check_docs.py`
- Create: `tests/test_release_docs.py`
- Modify: `README.md`（根）
- Modify: `docs/README.md`
- Modify: `docs/deployment.md`（仅同步引用，Docker 契约属 19.E）
- Modify: `output/README.md`
- Evidence: `output/evidence/release-cleanup/reference-inventory.json`（生成物，不入库）

## 步骤

1. **Step 1 清单先行**：扫描 `docs/tasks`、角色代号（TL/IA/IB/AA/AB/EX/DA/DB）、
   `verify_route`、旧算法名（actuated 作为正式算法出现处）、`1.5`/`--steps`
   36000/`--quick` 旧口径、历史"已完成"断言，写出
   `output/evidence/release-cleanup/reference-inventory.json`（不入库）。
2. **Step 2 重写公开文档**：根 README 以评委快速开始开头（原生一键启动 →
   支持算法与 canonical ID → 场景导入 → quick demo → 形式矩阵命令 →
   证据位置 → 原生部署 → Docker 部署 → not_run 状态声明）；四份 release
   文档分别覆盖：总览导航、实验协议（540-run、3600s+600s warmup、seeds、
   指标、安全门禁、统计判定规则）、证据合同（manifest/provenance/status/
   events/metrics/summary 字段与单位）、算法扩展指南。
3. **Step 3 边界检查器**：`scripts/release/check_docs.py --root .` 扫描公开
   文档（根 README、docs/README.md、docs/deployment.md、docs/release/*、
   output/README.md）：内部角色代号、`docs/tasks` 链接、`verify_route`、旧
   形式口径、`--quick`/`--steps` 秒数残留、个人绝对路径、无证据的 pass 声明
   必须零命中；本地链接必须存在。`tests/test_release_docs.py` 用 pytest 锁定
   同一规则集并对检查器自检（干净仓库通过、注入违规文件失败）。
4. **Step 4 门禁与提交**：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_release_docs.py -q
.\.venv\Scripts\python.exe scripts/release/check_docs.py --root .
git add -- README.md docs/README.md docs/deployment.md docs/release `
  scripts/release/check_docs.py tests/test_release_docs.py output/README.md
git diff --cached --name-status; git diff --cached --check
git diff --cached --name-only -- "赛题资料.7z" data/intersection_data
git commit -m "docs: publish judge-facing release guidance"
```

## 停止条件与诚实边界

- 540-run 形式矩阵在 Task 22 执行前，所有文档只允许 `not_run`/`计划` 口径，
  禁止把计划写成结果。
- Docker live、第二环境保持 Task 19 的 `not_run` 声明，不在 Task 20 改写。
- 独立只读复审（本环境替代 Terra/Sol）CLEAN 后方可提交；发现项 test-first 修复。
