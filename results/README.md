# 实验输出

> 本目录存放仿真运行和实验产生的输出文件。**整体 gitignore，不纳入版本控制。**

## 组织方式（建议）

```
results/
├── baseline/          # 固定配时基线结果
├── algorithm/         # 算法控制结果
├── figures/           # 生成的图表
└── logs/              # 运行日志
```

## 命名规则

`<实验编号>_<路口>_<方案>_<重复次数>.xml`
如：`E01_intersection1_fixed_run1_tripinfo.xml`

## 复现方式

实验参数见 `configs/`，运行脚本见 `scripts/`。
