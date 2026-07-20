# 贡献指南

> 本文说明 Git 工作流、提交规范和协作流程。

## Git 工作流（三阶段渐进）

### Phase 1：当前 ~ 第 2 周

- `main` 为保护分支，普通成员不直接 push
- 各组使用固定分支：`docs/a-team`、`docs/b-team`、`docs/c-team`、`docs/d-team`
- 组员在组分支上 commit + push
- 各组 Owner 每 2-3 天 merge 到 main

日常操作：
```bash
git switch docs/a-team       # 切到组分支
git pull origin docs/a-team  # 拉取最新
# ... 编辑文件 ...
git add <文件>
git commit -m "docs(A): 完成路口1数据档案"
git push origin docs/a-team
```

Owner 合并：
```bash
git switch main
git pull origin main
git merge docs/a-team
git push origin main
```

### Phase 2：第 3 周起

- 引入 `develop` 分支，`docs/*` 分支归档
- 功能分支命名：`feature/<描述>`、`simulation/<描述>`、`fix/<描述>`
- 从 develop 创建，完成后 merge 回 develop
- main 只在里程碑节点从 develop 合并

### Phase 3：第 5 周起

- 功能分支通过 Pull Request 合并到 develop
- 至少 1 人 Review（看三点：能运行、不影响别人、命名规范）
- Squash merge

## Commit 规范

格式：`<type>(<scope>): <中文描述>`

| type | 场景 | 示例 |
|------|------|------|
| `docs` | 文档 | `docs(A): 完成路口1数据档案` |
| `feat` | 新功能 | `feat(B): 新增Webster算法框架` |
| `fix` | 修复 | `fix(A): 修复SUMO配置文件` |
| `chore` | 配置/维护 | `chore: 更新.gitignore` |

scope：`A` / `B` / `C` / `D` / `all`，或模块名。

规则：
- 一次 commit 只做一件事
- 不写 "update"、"修改" 等无信息量描述

## 文件命名

| 类型 | 规则 | 示例 |
|------|------|------|
| 目录名 | 英文小写 kebab-case | `docs/guides/` |
| 代码/脚本 | 英文小写 snake_case | `batch_simulation.py` |
| 对外文档 | 英文小写 kebab-case | `intersection-01.md` |
| 内部文档 | 允许中文 | `A组任务书.md` |
| 图片 | 英文小写 kebab-case | `intersection-01-map.png` |

禁止：文件名中使用空格、大写字母（英文部分）。

## Issue 规范

Labels：
- 组别：`group/A` `group/B` `group/C` `group/D`
- 类型：`task` `bug` `question`
- 优先级：`high` `normal` `low`

Issue 模板：
```markdown
## 描述
（一句话说清楚要做什么）

## 所属小组
（A/B/C/D）

## 验收标准
- [ ] 标准1
- [ ] 标准2
```

## 提交文档前 Checklist

- [ ] 文件放在正确目录
- [ ] 文件命名符合规范
- [ ] README 已同步更新（如有需要）
- [ ] 图片能够正常显示
- [ ] 仓库内链接可以正常跳转
- [ ] Markdown 预览正常
