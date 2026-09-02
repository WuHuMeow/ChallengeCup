const ALGORITHM_NAMES: Record<string, string> = {
  fixed_time: "固定配时基线",
  actuated: "感应控制基线",
  classic_maxpressure: "经典最大压力控制",
  capacity_aware_maxpressure: "容量感知最大压力控制",
};

const METRIC_NAMES: Record<string, string> = {
  avg_queue_length: "平均排队长度",
  max_queue_length: "最大排队长度",
  throughput: "通行量",
  total_throughput: "总通行量",
  total_stops: "停车次数",
  avg_delay: "平均延误",
  avg_travel_time: "平均行程时间",
  fuel_ml: "燃油消耗",
  co2_g: "二氧化碳排放",
  collision_count: "碰撞次数",
  red_light_count: "闯红灯次数",
  illegal_transition_count: "非法相位切换次数",
  harsh_braking_count: "急刹车次数",
  teleport_count: "车辆传送次数",
  potential_conflict_count: "潜在冲突次数",
  current_phase: "当前相位编号",
  current_phase_name: "当前相位",
  elapsed_phase_time: "相位已持续时间",
  simulation_time: "仿真时间",
  vehicle_count: "车辆数",
  mean_speed: "平均速度",
};

const UNIT_NAMES: Record<string, string> = {
  vehicles: "辆",
  vehicle: "辆",
  seconds: "秒",
  second: "秒",
  count: "次",
  ml: "毫升",
  g: "克",
};

const STATUS_NAMES: Record<string, string> = {
  idle: "空闲",
  queued: "排队中",
  starting: "启动中",
  running: "运行中",
  stopping: "正在停止",
  completed: "已完成",
  stopped: "已停止",
  ended_early: "提前结束",
  disconnected: "连接中断",
  interrupted: "已中断",
  failed: "失败",
};

const CONNECTION_NAMES: Record<string, string> = {
  idle: "空闲",
  connecting: "连接中",
  connected: "已连接",
  disconnected: "已断开",
};

const VALIDATION_NAMES: Record<string, string> = {
  pass: "通过",
  fail: "未通过",
  warning: "有警告",
  pending: "待验证",
};

const SOURCE_KIND_NAMES: Record<string, string> = {
  net: "路网",
  route: "车流",
  routes: "车流",
  additional: "附加配置",
  config: "仿真配置",
};

const MESSAGE_NAMES: Record<string, string> = {
  "Realtime connection closed": "实时连接已关闭",
  "Realtime connection closed before the demo completed": "演示完成前实时连接已关闭",
  "Judge sequence stopped by the user": "评审序列已由用户停止",
  "Judge demo timed out before terminal status": "评审演示在到达终止状态前超时",
  "Native SUMO GUI unavailable": "原生 SUMO 界面不可用",
  "GUI delay is available only while a run is running": "仅可在仿真运行时调整 GUI 步进延迟",
  "GUI delay is unavailable for this run": "此运行不支持 GUI 步进延迟",
  "GUI delay is unavailable for a headless run": "无界面仿真不支持 GUI 步进延迟",
  "GUI delay control is unavailable for this runner": "此仿真运行器不支持 GUI 步进延迟控制",
  "display unavailable": "显示环境不可用",
  "frame unavailable": "SUMO 画面暂不可用",
  "judge requested stop": "评审端请求停止",
  "stop requested": "已请求停止仿真",
  "run cannot be stopped": "当前运行已结束，无法再次停止",
  "source warning: sumocfg does not explicitly reference flow input": "源配置未显式引用流量输入文件",
  "source warning: sumocfg does not explicitly reference turn input": "源配置未显式引用转向输入文件",
};

export function algorithmName(key: string, fallback = key): string {
  return ALGORITHM_NAMES[key] ?? fallback;
}

export function metricName(key: string): string {
  return METRIC_NAMES[key] ?? key.replace(/_/g, " ");
}

export function unitName(unit: string): string {
  return UNIT_NAMES[unit] ?? unit;
}

export function statusName(status: string): string {
  return STATUS_NAMES[status] ?? status;
}

export function connectionName(connection: string): string {
  return CONNECTION_NAMES[connection] ?? connection;
}

export function validationName(status: string): string {
  return VALIDATION_NAMES[status] ?? status;
}

export function sourceKindName(kind: string): string {
  return SOURCE_KIND_NAMES[kind] ?? kind;
}

export function localizeMessage(message: string): string {
  return MESSAGE_NAMES[message] ?? message;
}
