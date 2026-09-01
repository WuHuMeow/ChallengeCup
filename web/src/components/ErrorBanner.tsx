import type { RunError } from "../state/runStore";
import { localizeMessage } from "../localization";

interface ErrorBannerProps {
  error: RunError | null;
  onDismiss: () => void;
  onReconnect?: () => void;
}

export function ErrorBanner({ error, onDismiss, onReconnect }: ErrorBannerProps) {
  if (!error) return null;
  return (
    <div className="error-banner" role="alert">
      <span>{localizeMessage(error.message)}</span>
      <button type="button" onClick={onDismiss} aria-label="关闭错误提示" title="关闭错误提示">
        关闭
      </button>
      {error.kind === "disconnected" && onReconnect && (
        <button type="button" onClick={onReconnect}>重新连接事件流</button>
      )}
    </div>
  );
}
