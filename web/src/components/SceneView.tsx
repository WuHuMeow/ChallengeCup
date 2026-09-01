import type { SceneManifest } from "../api/client";
import { localizeMessage, sourceKindName, validationName } from "../localization";

interface SceneViewProps {
  scenes: SceneManifest[];
  loading?: boolean;
  error?: string | null;
}

function displayFileName(file: string): string {
  return file.replace(/\\/g, "/").split("/").pop() ?? file;
}

export function SceneView({ scenes, loading = false, error = null }: SceneViewProps) {
  const allVerified = scenes.length > 0 && scenes.every((scene) => scene.validation_status === "pass");
  return (
    <main className="judge-view scene-view">
      <div className="view-heading">
        <div>
          <p className="eyebrow">可复现场景清单</p>
          <h2>场景清单</h2>
        </div>
        <span className={allVerified ? "evidence-badge" : "review-badge"}>{allVerified ? "所有清单均已通过" : "请检查清单状态"}</span>
      </div>
      {loading && <p role="status">正在加载场景清单…</p>}
      {error && <p className="inline-error" role="alert">{localizeMessage(error)}</p>}
      {!loading && !error && scenes.length === 0 && <p className="empty-state">暂无场景清单。</p>}
      {!loading && !error && scenes.map((scene) => (
        <article className="scene-manifest" key={scene.scene_id}>
          <div className="scene-manifest__heading">
            <div>
              <p className="eyebrow">路口 {scene.intersection_id}</p>
              <h3>{scene.name}</h3>
            </div>
            <span className={`validation validation-${scene.validation_status}`}>{validationName(scene.validation_status)}</span>
          </div>
          <p>{scene.description}</p>
          <dl className="scene-facts">
            <div><dt>仿真步长</dt><dd>{scene.step_length} 秒</dd></div>
            <div><dt>交通信号灯</dt><dd>{scene.tls_ids.length}</dd></div>
            <div><dt>车道</dt><dd>{scene.lane_ids.length}</dd></div>
            <div><dt>交通流向</dt><dd>{scene.movement_count}</dd></div>
          </dl>
          <section className="provenance" aria-labelledby={`provenance-${scene.scene_id}`}>
            <h4 id={`provenance-${scene.scene_id}`}>源文件与 SHA-256</h4>
            <ul>
              {Object.entries(scene.source_files).map(([kind, file]) => (
                <li key={kind}><span>{sourceKindName(kind)}</span><code>{displayFileName(file)}</code><code>{scene.sha256[kind] ?? "不可用"}</code></li>
              ))}
            </ul>
          </section>
          {scene.warnings.length > 0 && (
            <section className="scene-warnings" aria-label="场景警告">
              <h4>警告</h4>
              <ul>{scene.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
            </section>
          )}
        </article>
      ))}
    </main>
  );
}
