import type { RunError } from "../state/runStore";

interface ErrorBannerProps {
  error: RunError | null;
  onDismiss: () => void;
  onReconnect?: () => void;
}

export function ErrorBanner({ error, onDismiss, onReconnect }: ErrorBannerProps) {
  if (!error) return null;
  return (
    <div className="error-banner" role="alert">
      <span>{error.message}</span>
      <button type="button" onClick={onDismiss} aria-label="Dismiss error" title="Dismiss error">
        Dismiss
      </button>
      {error.kind === "disconnected" && onReconnect && (
        <button type="button" onClick={onReconnect}>Reconnect events</button>
      )}
    </div>
  );
}
