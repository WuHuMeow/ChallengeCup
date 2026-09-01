# SUMO 对向放行时左转等待问题调研

> 调研日期：2026-08-31
> 范围：只研究信号相位层面的最小安全处理，不修改原始路网、路线或流量数据。

## 结论

当对向进口同时为绿灯时，左转车辆等待对向直行车辆通过，是 SUMO 对“许可左转”的正常建模，不是仿真卡死。SUMO 用小写 `g` 表示“绿灯但无优先权”，车辆必须给更高优先级的冲突流让行；大写 `G` 才表示有通行优先权。

如果要求左转车辆不再等待对向直行流，安全做法必须让冲突的对向直行变红，并给左转一个保护放行阶段。不能在对向直行仍为 `G` 时，把左转从 `g` 直接改成 `G`。

对本项目当前车道结构，最小且稳妥的算法级方案是已经采用的 `incoming` 思路：每次只放行一个进口，该进口的直行、左转和右转都为 `G`，随后经过黄灯和全红再切换到下一进口。它不需要修改路网，也不会出现同一共享车道中“直行红、左转绿”的队头阻塞。

## SUMO 官方行为

SUMO 官方文档明确说明：

- 低速路口可以同时放行对向直行与左转，但左转必须让行；这种状态称为 `green minor`，在状态字符串中使用小写 `g`。
- 小写 `g` 表示没有优先权，车辆只有在没有更高优先级冲突车辆时才可通过。
- 大写 `G` 表示有优先权的绿灯。
- 要取消左转让行，需要保护左转阶段；SUMO 自动生成程序的保护左转时长默认是 6 秒，可用 `--tls.left-green.time` 调整。
- 如果没有专用转向车道，SUMO 可能无法安全构造单独的保护左转阶段，因此仍会使用许可左转。

来源：

- [SUMO Traffic Lights：自动生成程序、许可左转和保护左转](https://sumo.dlr.de/docs/Simulation/Traffic_Lights.html#automatically_generated_tls-programs)
- [SUMO Traffic Lights：信号状态 `g` 与 `G`](https://sumo.dlr.de/docs/Simulation/Traffic_Lights.html#signal_state_definitions)
- [netconvert：`--tls.left-green.time`、`--tls.layout`、`--tls.no-mixed`](https://sumo.dlr.de/docs/netconvert.html#tls_building)

## 本项目的实际证据

场景 1 的源路网绿灯状态包含：

```text
GGGGgrrrrGGGGgrrrr
```

其中小写 `g` 对应左转连接，所以对向直行车辆存在时，左转车辆必须等待。路网的 `request/foes/response` 矩阵也为这些左转连接配置了冲突让行关系。

场景 1 同时存在共享车道：

- 东进口车道 `-E1_1` 同时连接直行 `linkIndex=7` 和左转 `linkIndex=8`。
- 西进口车道 `E0_1` 同时连接直行 `linkIndex=16` 和左转 `linkIndex=17`。
- 南北进口也有相同的共享车道结构。

SUMO 官方文档说明，信号状态控制的是 lane-to-lane link，而不是整条 lane，因此同一车道可以出现多个信号。如果一个连接为红、另一个连接为绿，排在最前面的红灯车辆可能阻挡后方绿灯车辆。`netconvert --tls.no-mixed` 正是用于避免同一车道的不同连接在一个相位里混用红灯与绿灯。

来源：

- [SUMO Traffic Lights：信号控制 link，而非 lane](https://sumo.dlr.de/docs/Simulation/Traffic_Lights.html#signal_state_definitions)
- [netconvert：避免同车道红绿混合的 `--tls.no-mixed`](https://sumo.dlr.de/docs/netconvert.html#tls_building)

## 可选方案比较

| 方案 | 左转是否等待 | 安全性 | 是否修改路网 | 影响 |
|---|---|---|---|---|
| 保留对向同时放行，左转使用 `g` | 会等待冲突直行 | 安全，符合许可左转规则 | 否 | 通行能力较高，但左转体验取决于对向车流空隙 |
| 对向同时为 `G`，把左转也直接改成 `G` | 表面上不等待 | 不安全，不应采用 | 否 | 同时给予冲突流优先权，可能造成碰撞或错误冲突关系 |
| 单独保护左转，只给左转 `G` | 不等待对向直行 | 有专用左转车道时安全 | 通常需要 | 当前共享车道可能被前方直行车阻挡 |
| 每次只放行一个进口，该进口全部为 `G` | 不等待对向直行 | 安全 | 否 | 最小、稳妥，但对向直行不能同时利用绿灯 |
| 对向许可相位后增加单进口保护尾段 | 许可阶段会让行，尾段不让行 | 安全 | 否 | 通行能力与左转保障的折中，但相位与绿时分配更复杂 |

## 最小推荐

### 当前目标是“消除转弯等待”

继续使用当前算法已经生成的单进口放行状态，不再修改代码。完整停止并重启 API/演示服务后重新发起仿真，确保新进程加载当前 `fixed_time_plan.py`；已有运行目录中的 `signal_program.add.xml` 是冻结产物，不会被代码修改自动更新。

当前解析器为场景 1 生成的四个服务绿灯状态是：

```text
rrrrrGGGGrrrrrrrrr
rrrrrrrrrrrrrrGGGG
GGGGGrrrrrrrrrrrrr
rrrrrrrrrGGGGGrrrr
```

每个状态只放行一个进口，且该进口所有连接均为大写 `G`。这种布局与 SUMO 官方 `--tls.layout incoming` 的定义一致：每个进口单独拥有一个绿灯阶段，所有转向均允许通行。

来源：[SUMO Traffic Lights：Phase layout incoming](https://sumo.dlr.de/docs/Simulation/Traffic_Lights.html#phase_layout_incoming)

### 如果后续更重视通行效率

可以仅在相位生成算法内增加“许可主相位 + 单进口保护尾段”：

1. 对向直行同时放行，左转保持小写 `g`，允许在安全空隙中提前通过。
2. 主相位结束后，依次给每个进口一个较短的保护尾段；这个进口的直行、左转、右转同时保持 `G`，对向全部为红。
3. 从原有主绿灯中扣除保护尾段时间，保持 Excel 总周期不变。
4. 黄灯和全红阶段继续保留。

这比单进口全周期放行更高效，但已经不是“无需调整的最小修复”，需要重新验证周期分配、平均延误、排队长度和碰撞数。

## 不建议的操作

- 不要仅把状态字符串中的 `g` 批量替换为 `G`。
- 不要让互相冲突的直行和左转同时使用大写 `G`。
- 不要在共享车道上设置“直行红、左转绿”的独立保护阶段，除非同一进口的直行也保持放行，或路网确实具有不会被直行队列阻挡的专用左转车道。
- 不要把 `tlsCoordinator.py` 当成本问题的修复工具。该工具用于多个信号控制器之间的绿波偏移协调，不负责解决单个路口内部的许可左转冲突。

SUMO 官方还提醒：新引入 `g/G` 让行关系时，只有通过 `netconvert` 重新加载网络和新信号方案，才能确保底层路权矩阵与新关系一致。因此，纯算法修改应优先复用路网已有的冲突关系，避免发明新的冲突 `g/G` 组合。

来源：[SUMO Traffic Lights：信号方案与路权规则的交互](https://sumo.dlr.de/docs/Simulation/Traffic_Lights.html#interaction_between_signal_plans_and_right-of-way_rules)
