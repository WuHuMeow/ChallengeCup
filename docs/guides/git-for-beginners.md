---
title: Git 入门指南
author: D组
created: 2026-07-20
group: D
status: final
---

# Git 入门指南

> 预计用时：10 分钟。覆盖日常协作所需的全部操作。

## 基本概念

| 概念 | 解释 |
|------|------|
| Repository（仓库） | 整个项目的文件夹 + 历史记录 |
| Commit（提交） | 一次保存，类似"存档点" |
| Branch（分支） | 平行的工作线，互不影响 |
| Merge（合并） | 把一条分支的工作合入另一条 |
| Remote（远程） | GitHub 上的仓库副本 |

## 每天的标准操作

```bash
# 1. 切到你的组分支
git switch docs/a-team

# 2. 拉取最新（防止和别人冲突）
git pull origin docs/a-team

# 3. 正常编辑文件...

# 4. 查看改了什么
git status

# 5. 添加要提交的文件
git add docs/intersections/intersection-01.md

# 6. 提交
git commit -m "docs(A): 完成路口1数据档案"

# 7. 推送到远程
git push origin docs/a-team
```

## 常见错误与解决

### push 被拒绝（rejected）

原因：别人先 push 了新内容。

```bash
git pull origin docs/a-team   # 先拉取
# 如果没有冲突，直接再 push
git push origin docs/a-team
```

### 不小心 commit 了错误的文件

```bash
# 撤销最近一次 commit（保留文件修改）
git reset --soft HEAD~1
# 重新选择文件提交
git add <正确的文件>
git commit -m "docs(A): 正确的描述"
```

### 不小心修改了不该改的文件

```bash
# 丢弃某个文件的修改（恢复到上次 commit 的状态）
git checkout -- intersection_data/1/sumo工程/demo_1.net.xml
```

### 冲突（conflict）

```bash
git pull origin docs/a-team
# 如果提示 CONFLICT：
# 1. 打开冲突文件，找到 <<<< ==== >>>> 标记
# 2. 手动选择保留哪部分
# 3. 保存后：
git add <冲突文件>
git commit -m "fix: 解决合并冲突"
```

## 注意事项

- 不要直接 push main（那是 Owner 的事）
- 不要修改 `intersection_data/1~20/` 中的文件
- commit 之前先 `git status` 确认没有多余文件
- 一次 commit 只做一件事
