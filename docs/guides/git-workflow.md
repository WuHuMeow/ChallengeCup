# 常见仓库上传方法

本指南面向不熟悉 Git 的队友，说明如何把本地修改上传到 GitHub 仓库、如何同步他人更新、以及常见问题的处理。

---

## 1. 前置准备

### 安装 Git

- Windows：下载 [Git for Windows](https://git-scm.com/download/win) 安装。
- macOS：`brew install git`
- Linux：`sudo apt-get install git` 或 `sudo yum install git`

### 配置用户名和邮箱

```bash
git config --global user.name "你的名字"
git config --global user.email "你的邮箱"
```

### 克隆仓库到本地

```bash
git clone https://gitee.com/fyx0927/challenge-cup.git
cd challenge-cup
```

---

## 2. 日常上传流程

每次修改完文件后，按以下顺序提交：

```bash
# 1. 查看当前修改了哪些文件
git status

# 2. 把所有修改加入暂存区
git add .

# 3. 写提交说明并提交到本地
git commit -m "docs: 修改了 XXX"

# 4. 推送到 GitHub
git push origin main
```

### 提交信息规范

建议采用 `类型: 描述` 的格式：

| 类型 | 用途 |
|------|------|
| `feat` | 新功能 |
| `fix` | 修复 bug |
| `docs` | 文档修改 |
| `refactor` | 代码重构 |
| `test` | 添加测试 |
| `chore` | 杂项、依赖更新 |

示例：

```bash
git commit -m "feat: 实现固定配时算法"
git commit -m "docs: 更新成员3任务书"
git commit -m "fix: 修复 runner.py 断点续跑逻辑"
```

---

## 3. 同步他人更新

在修改前，先拉取最新代码，避免冲突：

```bash
git pull origin main
```

如果本地已有未提交的修改，建议先提交再拉取：

```bash
git add .
git commit -m "docs: 保存本地修改"
git pull origin main
```

---

## 4. 冲突处理

当两个人同时修改了同一个文件的同一处，Git 会产生冲突。命令行会提示类似：

```text
Auto-merging README.md
CONFLICT (content): Merge conflict in README.md
Automatic merge failed; fix conflicts and then commit the result.
```

### 解决步骤

1. 打开冲突文件，找到如下标记：

```text
<<<<<<< HEAD
你本地的内容
=======
远程仓库的内容
>>>>>>> main
```

2. 保留需要的内容，删除 `<<<<<<< HEAD`、`=======`、`>>>>>>> main` 标记。
3. 保存文件。
4. 重新提交：

```bash
git add .
git commit -m "fix: 解决合并冲突"
git push origin main
```

---

## 5. 只上传特定文件

如果不希望一次性提交所有修改，可以指定文件：

```bash
git add README.md docs/team/成员1-仿真引擎/任务书.md
git commit -m "docs: 更新 README 和成员1任务书"
git push origin main
```

---

## 6. 查看历史记录

```bash
# 简洁历史
git log --oneline -10

# 查看某文件的修改历史
git log --oneline -- README.md
```

---

## 7. 撤销本地修改（谨慎使用）

```bash
# 撤销某个文件的所有本地修改（未 add 时）
git checkout -- 文件名

# 撤销已经 add 但未 commit 的修改
git reset HEAD 文件名

# 撤销最近一次 commit（保留修改）
git reset --soft HEAD~1
```

---

## 8. 常用命令速查表

| 命令 | 作用 |
|------|------|
| `git status` | 查看当前仓库状态 |
| `git add .` | 添加所有修改到暂存区 |
| `git commit -m "说明"` | 提交到本地 |
| `git push origin main` | 推送到 GitHub |
| `git pull origin main` | 拉取最新代码 |
| `git log --oneline` | 查看提交历史 |
| `git clone <url>` | 克隆仓库 |

---

## 参考

- [Git 官方文档](https://git-scm.com/doc)
- [GitHub Hello World 教程](https://docs.github.com/zh/get-started/quickstart/hello-world)
