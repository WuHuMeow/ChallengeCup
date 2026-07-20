# 引用方法

本指南说明在 README、任务书、报告等文档中引用文献、图片、代码和内部文件的方法。

---

## 1. 引用文献

###  footnote 式（推荐用于报告）

```markdown
XGBoost 是一种常用的梯度提升算法[^1]。

[^1]: Chen T, Guestrin C. XGBoost: A Scalable Tree Boosting System. KDD 2016.
```

效果：

XGBoost 是一种常用的梯度提升算法[^1]。

[^1]: Chen T, Guestrin C. XGBoost: A Scalable Tree Boosting System. KDD 2016.

### 列表式（推荐用于 README）

```markdown
## 参考

- [1] Chen T, Guestrin C. XGBoost: A Scalable Tree Boosting System. KDD 2016.
- [2] SUMO 官方文档. https://www.eclipse.org/sumo/
```

---

## 2. 引用图片

图片应放在项目内部，避免使用外部图床链接，防止失效。

```markdown
![系统架构](./superpowers/specs/images/architecture.png)
```

### 图片规范

| 项目 | 建议 |
|------|------|
| 格式 | `.svg` 优先，其次 `.png` |
| 路径 | 使用相对路径 |
| 命名 | 英文小写，用下划线连接，如 `architecture.svg` |
| 说明 | 每个图片都应有 alt 文字 |

---

## 3. 引用代码

### 引用本仓库代码

```markdown
详见 [`algorithms/fixed_time.py`](../../algorithms/fixed_time.py) 中的 `FixedTimeAlgorithm` 实现。
```

### 引用外部代码

如果是参考了外部代码，请在文件头部或 README 中注明来源：

```markdown
## 代码参考

本模块参考了 SUMO 官方 TraCI 教程：
https://sumo.dlr.de/docs/TraCI.html
```

---

## 4. 引用内部文档

### 相对路径写法

```markdown
详见 [系统设计文档](./superpowers/specs/2026-07-14-xiongan-vehicle-road-cloud-design.md)。
```

### 引用其他目录 README

```markdown
各模块详情见对应目录下的 [README.md](../../algorithms/README.md)。
```

---

## 5. 引用赛题 PDF

```markdown
根据 [赛题 PDF](../pdf/XH-202613_面向雄安新区“城市大脑”的车路云.pdf) 第八点要求……
```

---

## 6. 引用网页

```markdown
[SUMO 官方文档](https://www.eclipse.org/sumo/)
```

### 引用规范

- 优先使用稳定、权威的来源，如官方网站、知名论文。
- 避免引用个人博客或可能失效的链接。
- 若链接较长，可用 Markdown 链接语法隐藏：

```markdown
[SUMO 官方下载页](https://www.eclipse.org/sumo/)
```

---

## 7. 数据引用

在实验报告中引用项目数据时，写明路径和生成方式：

```markdown
实验数据保存在 `output/full_comparison.csv`，由 `experiments/runner.py` 运行 180 次仿真生成。
```

---

## 8. 常见错误

| 错误 | 正确 |
|------|------|
| `详见[这里](http://...)` | `详见 [SUMO 官方文档](http://...)` |
| `![图片]` | `![系统架构图](./images/architecture.svg)` |
| 使用绝对路径 `C:\Users\...\file.md` | 使用相对路径 `./docs/...` |
| 引用不存在的文件 | 提交前验证链接可访问 |

---

## 9. 验证链接

提交文档前，建议检查内部链接是否有效：

```bash
# 在仓库根目录运行，检查所有 markdown 链接
python - <<'PY'
import re
from pathlib import Path

for md in Path('.').rglob('*.md'):
    text = md.read_text(encoding='utf-8')
    for label, target in re.findall(r'\[([^\]]+)\]\(([^)]+)\)', text):
        if target.startswith(('http', '#', 'mailto:')):
            continue
        if not (md.parent / target).resolve().exists():
            print(f"BROKEN: {md} -> [{label}]({target})")
PY
```

---

## 参考

- [GitHub 基本撰写和格式语法](https://docs.github.com/zh/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github)
- [学术论文引用格式（GB/T 7714）](https://www.nstl.gov.cn/docs/20171116101826546288.pdf)
