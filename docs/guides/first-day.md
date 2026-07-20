---
title: 新人第一天指南
author: D组
created: 2026-07-20
group: D
status: final
---

# 新人第一天指南

> 预计用时：15 分钟。完成后即可正式开始参与项目。

## Step 1: Clone 仓库（2 分钟）

```bash
git clone https://github.com/<org>/xiong-an-traffic.git
cd xiong-an-traffic
```

## Step 2: 阅读 README（3 分钟）

打开根目录 `README.md`，快速了解：
- 项目做什么
- 目录结构
- 你在哪个组

## Step 3: 安装 SUMO（5 分钟）

1. 下载：https://sumo.dlr.de/docs/Downloading.php
2. 安装（Windows 建议用安装包）
3. 配置环境变量 `SUMO_HOME`：
   - Windows：系统环境变量 → 新建 `SUMO_HOME` = `C:\Program Files\Eclipse\Sumo`
4. 验证：
```bash
sumo --version
```

## Step 4: 配置 Python 环境（3 分钟）

```bash
# 方式一：pip
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt

# 方式二：conda
conda env create -f environment.yml
conda activate xiong-an-traffic
```

## Step 5: 切换到你的组分支（1 分钟）

```bash
git switch docs/a-team    # A 组
git switch docs/b-team    # B 组
git switch docs/c-team    # C 组
git switch docs/d-team    # D 组
```

## Step 6: 完成第一次 Commit（1 分钟）

实际练习：
```bash
echo "# 我的第一篇文档" > docs/guides/my-first-doc.md
git add docs/guides/my-first-doc.md
git commit -m "docs(X): 完成新人第一次提交练习"
git push origin docs/x-team
```

提交后可以删除这个练习文件。

## Step 7: 阅读你的组任务书

- A 组：`docs/A组任务书_数据与仿真组.md`
- B 组：`docs/B组任务书_算法研究组.md`
- C 组：`docs/C组任务书_实验评估组.md`
- D 组：`docs/D组任务书_项目管理与文档组.md`

## 完成！

到这里你已经：
- 有了完整的本地环境
- 能运行 SUMO
- 知道自己在哪个分支工作
- 完成了第一次 commit
- 知道自己的任务是什么

有问题？查看 [FAQ](../faq/README.md) 或在群里问你的组 Owner。
