import { useState } from "react";
import { MonitorPlay, Play, Square } from "lucide-react";
import type { AlgorithmSpec, JudgeApiClient, SceneManifest } from "../api/client";
import { algorithmName, connectionName, localizeMessage, statusName } from "../localization";
import type { RunStoreSnapshot } from "../state/runStore";
import { ErrorBanner } from "./ErrorBanner";
import { MetricPanel } from "./MetricPanel";

interface SimulationViewProps {
  api: JudgeApiClient;
  snapshot: RunStoreSnapshot;
  scenes: SceneManifest[];
  algorithms: AlgorithmSpec[];
  startPending: boolean;
  guiDelayPending: boolean;
  onStart: () => void;
  onStop: () => void;
  onNativeGui: () => void;
  onGuiDelayChange: (delayMs: number) => void;
  onSceneChange: (sceneId: string) => void;
  onAlgorithmChange: (algorithm: string) => void;
  onSelectionChange: (selection: Partial<Pick<RunStoreSnapshot, "selectedLoad" | "selectedSeed" | "selectedDuration" | "selectedWarmup" | "selectedStepLength" | "selectedDisturbance">>) => void;
  onReconnect: () => void;
  onDismissError: () => void;
}

export function SimulationView({
  snapshot,
  scenes,
  algorithms,
  startPending,
  guiDelayPending,
  onStart,
  onStop,
  onNativeGui,
  onGuiDelayChange,
  onSceneChange,
  onAlgorithmChange,
  onSelectionChange,
  onReconnect,
  onDismissError,
}: SimulationViewProps) {
  const presetStepLengths = [0.1, 0.5, 1];
  const [customStepLengthVisible, setCustomStepLengthVisible] = useState(
    !presetStepLengths.includes(snapshot.selectedStepLength),
  );
  const active = Boolean(snapshot.activeRun);
  const guiDelayLocked = ["queued", "starting", "stopping"].includes(snapshot.activeRun?.status ?? "");
  const guiDelayDisabled = startPending || guiDelayPending || guiDelayLocked;
  const stepLength = snapshot.selectedStepLength > 0 ? snapshot.selectedStepLength : 1;
  const targetSeconds = Math.max(0, snapshot.selectedDuration);
  const progressSeconds = Math.min(targetSeconds, Math.max(0, snapshot.runSimulationTime ?? 0));
  const targetSteps = Math.ceil(targetSeconds / stepLength);
  const completedSteps = Math.min(targetSteps, Math.floor((progressSeconds + Number.EPSILON) / stepLength));
  const formatNumber = (value: number) => Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
  return (
    <main className="simulation-view">
      <div className="view-heading">
        <div>
          <p className="eyebrow">评审流程</p>
          <h2>实时仿真</h2>
        </div>
        <span className="demo-badge">快速演示输出</span>
      </div>
      <p className="evidence-note">仅展示由证据接口验证的单次运行封存结果；正式矩阵结论需等待任务 22 完成。</p>
      <ErrorBanner error={snapshot.error} onDismiss={onDismissError} onReconnect={onReconnect} />
      <section className="control-panel" aria-label="仿真控制">
        <label>
          场景
          <select value={snapshot.selectedScene} onChange={(event) => onSceneChange(event.target.value)}>
            {(scenes.length ? scenes : [{ scene_id: "1", intersection_id: "1", name: "Intersection 1" } as SceneManifest]).map((scene) => (
              <option key={scene.scene_id} value={scene.intersection_id}>{scene.name}</option>
            ))}
          </select>
        </label>
        <label>
          算法
          <select value={snapshot.selectedAlgorithm} onChange={(event) => onAlgorithmChange(event.target.value)}>
            {(algorithms.length ? algorithms : [{ key: "fixed_time", display_name: "Fixed Time" } as AlgorithmSpec]).map((algorithm) => (
              <option key={algorithm.key} value={algorithm.key}>{algorithmName(algorithm.key, algorithm.display_name)}</option>
            ))}
          </select>
        </label>
        <label>
          流量倍率
          <input type="number" min="0.5" max="2" step="0.25" value={snapshot.selectedLoad} onChange={(event) => onSelectionChange({ selectedLoad: Number(event.target.value) })} />
        </label>
        <label>
          随机种子
          <input type="number" min="0" step="1" value={snapshot.selectedSeed} onChange={(event) => onSelectionChange({ selectedSeed: Number(event.target.value) })} />
        </label>
        <label>
          仿真时长（秒）
          <input type="number" min="5" max="3600" step="5" value={snapshot.selectedDuration} onChange={(event) => onSelectionChange({ selectedDuration: Number(event.target.value) })} />
        </label>
        <label>
          预热时长（秒）
          <input type="number" min="0" max={Math.max(0, snapshot.selectedDuration - 1)} step="5" value={snapshot.selectedWarmup} onChange={(event) => onSelectionChange({ selectedWarmup: Number(event.target.value) })} />
        </label>
        <label>
          扰动设置
          <select value={snapshot.selectedDisturbance} onChange={(event) => onSelectionChange({ selectedDisturbance: event.target.value as RunStoreSnapshot["selectedDisturbance"] })}>
            <option value="none">无</option>
            <option value="construction">道路施工封闭</option>
            <option value="event_demand">活动交通需求</option>
            <option value="vehicle_failure">车辆故障</option>
          </select>
        </label>
        <fieldset className="step-length-control">
          <legend>仿真步长（秒）</legend>
          <div className="step-length-actions">
            {presetStepLengths.map((value) => (
              <button
                key={value}
                type="button"
                aria-label={`${value} 秒步长`}
                aria-pressed={!customStepLengthVisible && snapshot.selectedStepLength === value}
                onClick={() => {
                  setCustomStepLengthVisible(false);
                  onSelectionChange({ selectedStepLength: value });
                }}
              >
                {value} 秒
              </button>
            ))}
            <button
              type="button"
              aria-label="自定义步长"
              aria-pressed={customStepLengthVisible}
              onClick={() => setCustomStepLengthVisible(true)}
            >
              自定义
            </button>
          </div>
          {customStepLengthVisible && (
            <label htmlFor="custom-step-length">
              自定义仿真步长（秒）
              <input
                id="custom-step-length"
                type="number"
                min="0.01"
                step="0.01"
                value={snapshot.selectedStepLength}
                onChange={(event) => onSelectionChange({ selectedStepLength: Number(event.target.value) })}
              />
            </label>
          )}
          <small>步长越小，仿真越精细、总步数越多。</small>
        </fieldset>
        <div className="gui-delay-control">
          <label htmlFor="gui-delay-ms">GUI 步进延迟（毫秒）</label>
          <div className="gui-delay-actions">
            <button
              type="button"
              aria-label="最快 0 毫秒"
              onClick={() => onGuiDelayChange(0)}
              disabled={guiDelayDisabled || snapshot.selectedGuiDelayMs === 0}
            >
              最快 0 ms
            </button>
            <button
              type="button"
              aria-label="延迟减少 50 毫秒"
              onClick={() => onGuiDelayChange(Math.max(0, snapshot.selectedGuiDelayMs - 50))}
              disabled={guiDelayDisabled || snapshot.selectedGuiDelayMs === 0}
            >
              −50 ms
            </button>
            <input
              id="gui-delay-ms"
              type="number"
              min="0"
              max="2000"
              step="50"
              value={snapshot.selectedGuiDelayMs}
              disabled={guiDelayDisabled}
              onChange={(event) => onGuiDelayChange(Number(event.target.value))}
            />
            <button
              type="button"
              aria-label="延迟增加 50 毫秒"
              onClick={() => onGuiDelayChange(Math.min(2000, snapshot.selectedGuiDelayMs + 50))}
              disabled={guiDelayDisabled || snapshot.selectedGuiDelayMs === 2000}
            >
              +50 ms
            </button>
          </div>
          <small>0 毫秒为最快；数值越大，原生 SUMO 画面移动越慢。</small>
        </div>
        <div className="button-row">
          <button type="button" onClick={onStart} disabled={startPending || (active && snapshot.connection !== "idle")}>
            <Play size={16} aria-hidden="true" /> 开始快速演示
          </button>
          <button type="button" onClick={onStop} disabled={!active}>
            <Square size={16} aria-hidden="true" /> 停止运行
          </button>
          <button type="button" onClick={onNativeGui} disabled={!active} title="显示原生 SUMO 界面">
            <MonitorPlay size={16} aria-hidden="true" /> 显示原生 SUMO 界面
          </button>
        </div>
      </section>
      <div className="status-strip" aria-live="polite">
        <span>状态：{statusName(snapshot.activeRun?.status ?? "idle")}</span>
        <span>连接：{connectionName(snapshot.connection)}</span>
        <span data-testid="simulation-progress">
          仿真进度：{completedSteps}/{targetSteps} 步（{formatNumber(progressSeconds)}/{formatNumber(targetSeconds)} 秒）
        </span>
        {snapshot.activeRun?.reason && <span>{localizeMessage(snapshot.activeRun.reason)}</span>}
      </div>
      <section className="simulation-grid">
        <MetricPanel metrics={snapshot.metrics} />
        <section className="safety-panel" aria-label="安全计数">
          <h2>安全计数</h2>
          {snapshot.safety ? (
            <dl>
              <div><dt>碰撞</dt><dd>{snapshot.safety.collision}</dd></div>
              <div><dt>闯红灯</dt><dd>{snapshot.safety.red_light}</dd></div>
              <div><dt>非法相位切换</dt><dd>{snapshot.safety.illegal_transition}</dd></div>
              <div><dt>急刹车</dt><dd>{snapshot.safety.harsh_braking}</dd></div>
              <div><dt>车辆传送</dt><dd>{snapshot.safety.teleport}</dd></div>
              <div><dt>潜在冲突</dt><dd>{snapshot.safety.potential_conflict}</dd></div>
            </dl>
          ) : <p>尚未收到安全观测数据</p>}
        </section>
        {typeof snapshot.metrics.current_phase_name === "string" && (
          <p className="phase-status">信号阶段：{snapshot.metrics.current_phase_name} · {typeof snapshot.metrics.elapsed_phase_time === "number" ? snapshot.metrics.elapsed_phase_time : 0} 秒</p>
        )}
      </section>
    </main>
  );
}
