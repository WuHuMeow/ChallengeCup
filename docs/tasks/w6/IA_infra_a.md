# 仿真基础设施 A（IA） W6 任务书

> 周期：8/24（周日）- 8/31（周六） | 核心目标：最终环境验证、提交材料中的工程文件准备、答辩支持
> **完成状态（2026-07-23）**：⬜ 未开始——全部任务待 W5 收尾后启动。

## 每日任务

### Day 1（8/24 周日）— 全员 review 会议

- [ ] 参加全员 review 会议
- [ ] 记录与仿真环境/Docker 相关的修改意见
- [ ] 把修改意见拆成可执行 issue 列表

**验证：** 形成环境/部署相关修改意见清单，每条有明确处理状态（待修/已修/不修）。

### Day 2（8/25 周一）— 修复 review 问题 + Docker 终验

- [ ] 修复 review 中发现的环境/部署问题
- [ ] 最终 Docker 验证：全新环境 build + run
- [ ] 确认镜像可导出（`docker save`）备用，应对答辩现场无网络场景

```bash
# 镜像导出备用
docker save ca-mp:latest -o ca-mp-latest.tar
ls -lh ca-mp-latest.tar
# 离线加载验证
docker load -i ca-mp-latest.tar
docker run --rm ca-mp:latest 1
```

**验证：** `ca-mp-latest.tar` 生成成功；离线 `docker load` 后 `docker run --rm ca-mp:latest 1` 退出码 0。

### Day 3（8/26 周二）— 工程文件准备

- [ ] 确认 20 路口数据完整（`data/intersection_data/{1-20}/sumo工程/` 五件齐全）
- [ ] 确认 `engine/configs/` 增强版 sumocfg 配置正确
- [ ] 确认 `data/intersection_data/metadata/intersections.yaml` 完整
- [ ] 如比赛要求 zip 打包，准备打包脚本（排除 `output/`、`__pycache__/`、`.git/`）

```bash
# 数据完整性快查
for n in $(seq 1 20); do
  d="data/intersection_data/$n/sumo工程"
  for ext in net.xml rou.xml flow.xml sumocfg turn.xml; do
    [ -f "$d/demo_$n.$ext" ] || echo "缺失: $d/demo_$n.$ext"
  done
done
```

**验证：** 上述脚本无任何"缺失"输出；打包脚本生成的 zip 不含 `output/`、`__pycache__/`、`.git/`。

### Day 4（8/27 周三）— 最终集成验证 + 临时文件清理

- [ ] 协助 TL 做最终集成验证
- [ ] 确认代码仓库中无多余文件（`page_*.png`、`temp_doc.pdf` 等临时文件删除）
- [ ] 确认提交包大小在限制内

```bash
# 临时文件清理检查
git ls-files | grep -E "page_.*\.png|temp_doc\.pdf|\.tmp$"   # 应无输出
du -sh .   # 记录仓库总大小
```

**验证：** `git ls-files | grep -E "page_.*\.png|temp_doc\.pdf"` 无输出；TL 侧最终集成验证通过。

### Day 5（8/28 周四）— 部署文档最终打印版

- [ ] 准备部署文档的最终打印版（如需要纸质材料）
- [ ] 确认所有环境配置说明准确（SUMO 版本、Docker 命令、依赖版本）
- [ ] 与 W5 的 `docs/deployment.md` 最终版交叉核对

**验证：** 打印版/PDF 版部署文档与仓库内 `docs/deployment.md` 内容一致，命令逐条可执行。

### Day 6（8/29 周五）— 模拟答辩

- [ ] 参加模拟答辩
- [ ] 准备可能被问到的环境问题及标准答案：
  - "SUMO 版本为什么选 1.27.1？"（统一最新版、向后兼容、修复了旧版 schema 问题）
  - "Docker 镜像多大？"（< 2GB，ubuntu:22.04 + apt sumo）
  - "迁移过程中遇到什么兼容性问题？"（XML schema 变化用 netconvert 重生成；步长不统一保留原值）
- [ ] 准备 1 分钟现场演示脚本（docker run 跑通路口 1）

**验证：** 模拟答辩中环境类问题回答流畅；现场演示脚本可在 2 分钟内跑通。

### Day 7（8/30-8/31）— 最终提交 + Buffer

- [ ] 协助最终提交（代码 + 工程文件 + 镜像 tar）
- [ ] Buffer：处理临场问题

**验证：** 提交材料齐套（代码 zip + 镜像 tar + 部署文档），TL 确认提交完成。

## 交付物

| 文件 | 截止日 | 验收标准 |
|------|--------|----------|
| Docker 最终验证 + 镜像 tar | 8/25 | 全新/离线环境可运行 |
| 工程文件完整 | 8/26 | 20 路口五件齐全 + metadata 完整 |
| 临时文件清理 | 8/27 | 仓库干净，无 `page_*.png` / `temp_doc.pdf` |
| 答辩环境问答 + 演示脚本 | 8/29 | 模拟答辩通过 |

## 协作对接

- 与 **TL** 完成最终集成验证与提交。
- 与 **DA/DB** 核对报告/视频中环境相关内容准确无误。
- 与 **EX/AA/AB** 同步答辩可能被问到的算法-环境交叉问题。
