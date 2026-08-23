import type { SceneManifest } from "../api/client";

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
          <p className="eyebrow">Reproducible scenario manifest</p>
          <h2>Scene</h2>
        </div>
        <span className={allVerified ? "evidence-badge" : "review-badge"}>{allVerified ? "All manifests pass" : "Review manifest status"}</span>
      </div>
      {loading && <p role="status">Loading scene manifest...</p>}
      {error && <p className="inline-error" role="alert">{error}</p>}
      {!loading && !error && scenes.length === 0 && <p className="empty-state">No scene manifests available.</p>}
      {!loading && !error && scenes.map((scene) => (
        <article className="scene-manifest" key={scene.scene_id}>
          <div className="scene-manifest__heading">
            <div>
              <p className="eyebrow">Intersection {scene.intersection_id}</p>
              <h3>{scene.name}</h3>
            </div>
            <span className={`validation validation-${scene.validation_status}`}>{scene.validation_status}</span>
          </div>
          <p>{scene.description}</p>
          <dl className="scene-facts">
            <div><dt>Step length</dt><dd>{scene.step_length} s</dd></div>
            <div><dt>Traffic lights</dt><dd>{scene.tls_ids.length}</dd></div>
            <div><dt>Lanes</dt><dd>{scene.lane_ids.length}</dd></div>
            <div><dt>Movements</dt><dd>{scene.movement_count}</dd></div>
          </dl>
          <section className="provenance" aria-labelledby={`provenance-${scene.scene_id}`}>
            <h4 id={`provenance-${scene.scene_id}`}>Source files and SHA-256</h4>
            <ul>
              {Object.entries(scene.source_files).map(([kind, file]) => (
                <li key={kind}><span>{kind}</span><code>{displayFileName(file)}</code><code>{scene.sha256[kind] ?? "Unavailable"}</code></li>
              ))}
            </ul>
          </section>
          {scene.warnings.length > 0 && (
            <section className="scene-warnings" aria-label="Scene warnings">
              <h4>Warnings</h4>
              <ul>{scene.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
            </section>
          )}
        </article>
      ))}
    </main>
  );
}
