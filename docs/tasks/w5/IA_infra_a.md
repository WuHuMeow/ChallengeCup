# 仿真基础设施 A（IA） W5 任务书

> 周期：8/17（周日）- 8/23（周六） | 核心目标：代码最终清理、Docker 最终验证、协助交付
> **完成状态（2026-07-23）**：⏳ 部分完成——✅ Day 1 代码清理（无调试/临时文件、无硬编码路径、`.gitignore` 已修正覆盖 SUMO 输出）、`requirements.txt` 已补 `defusedxml`；⬜ Docker 最终验证（Day 2）、部署文档外人复现测试（Day 3）、协助 DA/DB（Day 4）、最终集成验证（Day 6）待后续。

## 每日任务

### Day 1（8/17 周日）— 代码最终清理

- [x] 删除所有调试代码、临时文件（`page_*.png`、`temp_doc.pdf` 等）
- [x] 确认无硬编码路径（所有路径用相对路径或配置）
- [x] 确认 `.gitignore` 正确（不提交 `results/`、`__pycache__/`、`output/`）
- [x] 确认仓库结构干净，无未跟踪的散落文件

```bash
# 清理检查
git status --short                    # 应无意外未跟踪文件
grep -rn "C:/Users" --include="*.py" .  # 应无硬编码绝对路径
cat .gitignore | grep -E "results|__pycache__|output"
```

**验证：** `git status --short` 输出干净；`grep -rn "C:/Users" --include="*.py" .` 无匹配；`.gitignore` 包含 `results/`、`__pycache__/`、`output/`。

### Day 2（8/18 周一）— Docker 最终验证

- [ ] 在全新环境中执行 `docker build` + `docker run`
- [ ] 确认三种算法（ca_maxpressure / frap / mplight）都能在容器内运行
- [ ] 确认输出文件正确（tripinfo / stats / traj 三件齐全）
- [ ] 记录镜像大小、构建时间

```bash
# 三算法容器内验证
for algo in ca_maxpressure frap mplight; do
  docker run --rm -v ${PWD}/experiments/results:/app/experiments/results \
    ca-mp:latest python3 experiments/runner.py \
    --intersection 1 --algo $algo --seed 0 \
    --output-dir experiments/results/final/1/$algo
done
ls experiments/results/final/1/*   # 三个算法目录各有三件输出
```

**验证：** 三个算法目录各含 `tripinfo.xml + stats.xml + traj.xml`；镜像大小与构建时间记录在 `docs/deployment.md`。

### Day 3（8/19 周二）— 部署文档最终版

- [ ] 完善 `docs/deployment.md` 最终版：确认所有步骤可复现
- [ ] 添加"快速开始"章节（3 步跑通）
- [ ] 添加"完整实验复现"章节（360 组实验）
- [ ] 请一个非团队成员（如同学）按文档操作，验证可复现性

```markdown
<!-- docs/deployment.md 快速开始 -->
## 快速开始（3 步跑通）
1. `docker build -t ca-mp:latest -f docker/Dockerfile .`
2. `docker run --rm -v ${PWD}/output:/app/output ca-mp:latest 1`
3. 查看 `output/` 下的 tripinfo.xml / stats.xml / traj.xml
```

**验证：** 非团队成员仅按 `docs/deployment.md` 操作即可在 30 分钟内跑通路口 1，无需口头补充。

### Day 4（8/20 周三）— 协助 DA / DB

- [ ] 协助 DA：如果报告中"仿真环境搭建"章节需要补充技术细节
- [ ] 协助 DB：如果视频需要录制 Docker 部署过程
- [ ] 提供 SUMO 版本统一、迁移过程的素材

**验证：** DA 确认环境章节素材齐全；DB 完成 Docker 部署录屏（如需要）。

### Day 5（8/21 周四）— 最终代码 review

- [ ] 确认所有 Python 文件有 docstring
- [x] 确认 `requirements.txt` 完整（含 `defusedxml` 等本周新增依赖）
- [x] 确认 `README.md` 有项目简介和快速开始
- [ ] 提交最终代码给 TL

```bash
# requirements 完整性检查
pip install -r requirements.txt --dry-run
# docstring 抽查
python -c "import engine.runner, scenes.registry; print(engine.runner.__doc__[:20])"
```

**验证：** `pip install -r requirements.txt` 在干净虚拟环境中成功；`README.md` 含项目简介 + 快速开始两节。

### Day 6（8/22 周五）— 最终集成验证

- [ ] 协助 TL 做最终集成验证
- [ ] 确认 git 仓库状态干净（无未提交文件）
- [ ] 确认所有分支已合并到主干

**验证：** `git status` 输出 `nothing to commit, working tree clean`；TL 侧最终集成验证通过。

### Day 7（8/23 周六）— Buffer + 提交材料准备

- [ ] 处理遗留问题
- [ ] 准备提交材料中的"工程文件"部分（代码 + Docker + 文档清单）

**验证：** 提交材料清单中工程文件部分勾选完成。

## 交付物

| 文件 | 截止日 | 验收标准 |
|------|--------|----------|
| 代码清理完成 | 8/17 | 无调试代码、无临时文件、无硬编码路径 |
| Docker 最终验证 | 8/18 | 全新环境可运行，三算法均通过 |
| `docs/deployment.md` 最终版 | 8/19 | 外人可按文档复现（含快速开始 + 完整复现） |
| 仓库最终状态 | 8/22 | 干净、完整、`git status` 无未提交 |

## 协作对接

- 与 **TL** 完成最终集成验证与代码冻结。
- 与 **DA** 提供环境搭建章节技术细节。
- 与 **DB** 配合 Docker 部署录屏。
