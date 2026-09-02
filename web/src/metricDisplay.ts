const PRIORITY_METRICS = [
  "avg_delay",
  "avg_queue_length",
  "throughput",
  "total_throughput",
  "max_queue_length",
  "avg_travel_time",
  "total_stops",
  "fuel_ml",
  "co2_g",
] as const;

const DUPLICATE_OR_DERIVED_METRICS = new Set([
  "avg_delay_seconds",
  "avg_queue_length_vehicles",
  "max_queue_length_vehicles",
  "avg_travel_time_seconds",
  "completed_vehicle_count",
  "unfinished_vehicle_count",
  "fuel_consumption",
  "fuel_ml_per_completed",
  "co2_g_per_completed",
]);

export function selectDisplayMetrics(
  metrics: Record<string, unknown>,
): Array<readonly [string, unknown]> {
  const priorityKeys = new Set<string>(PRIORITY_METRICS);
  return [
    ...PRIORITY_METRICS
      .filter((key) => Object.prototype.hasOwnProperty.call(metrics, key))
      .map((key) => [key, metrics[key]] as const),
    ...Object.entries(metrics).filter(([key]) => (
      !priorityKeys.has(key) && !DUPLICATE_OR_DERIVED_METRICS.has(key)
    )),
  ];
}
