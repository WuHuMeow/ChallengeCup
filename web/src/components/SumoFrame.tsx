interface SumoFrameProps {
  src: string | null;
  sequence: number | null;
  simulationTime: number | null;
}

const EMPTY_PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADElEQVR42mNk+M/wHwAF/gL+e7QeVQAAAABJRU5ErkJggg==";

export function SumoFrame({ src, sequence, simulationTime }: SumoFrameProps) {
  return (
    <figure className="sumo-frame" data-testid="sumo-frame">
      <div className="sumo-frame__stage">
        <img src={src ?? EMPTY_PNG} alt="SUMO simulation frame" />
        {!src && <span className="sumo-frame__empty">Waiting for SUMO frame</span>}
      </div>
      <figcaption>
        <span data-testid="frame-sequence">Sequence {sequence ?? "-"}</span>
        <span data-testid="simulation-time">Simulation time {simulationTime ?? "-"} s</span>
      </figcaption>
    </figure>
  );
}
