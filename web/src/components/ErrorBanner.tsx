import type { RunError } from "../state/runStore";

interface ErrorBannerProps {
  error: RunError | null;
  onDismiss: () => void;
}

export function ErrorBanner({ error, onDismiss }: ErrorBannerProps) {
  if (!error) return null;
  return (
    <div className="error-banner" role="alert">
      <span>{error.message}</span>
      <button type="button" onClick={onDismiss} aria-label="Dismiss error" title="Dismiss error">
        Dismiss
      </button>
    </div>
  );
}
