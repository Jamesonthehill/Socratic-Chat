import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { label } from "./api";
export function Notice({ error, children }) {
  return error ? (
    <div className="notice error" role="alert">
      {error}
    </div>
  ) : children ? (
    <div className="notice" role="status">
      {children}
    </div>
  ) : null;
}
export function Badge({ value }) {
  return <span className={`badge ${value}`}>{label(value)}</span>;
}

export function GenerationStatus({ title = "BrainTutor", message, elapsedSeconds, ariaLabel, messageCard = false, fullScreen = false }) {
  const [localSeconds, setLocalSeconds] = useState(0);
  useEffect(() => {
    if (elapsedSeconds != null) return undefined;
    const started = Date.now();
    const timer = window.setInterval(() => setLocalSeconds((Date.now() - started) / 1000), 100);
    return () => window.clearInterval(timer);
  }, [elapsedSeconds]);
  const seconds = elapsedSeconds ?? localSeconds;
  const content = (
    <div
      className={`generation-status${messageCard ? " message socratic-thinking-message" : ""}${fullScreen ? " generation-status-fullscreen" : ""}`}
      role={fullScreen ? undefined : "status"}
      aria-label={fullScreen ? undefined : ariaLabel || `${title}: ${message}`}
    >
      <span className="thinking-mark" aria-hidden="true">
        <svg viewBox="0 0 44 44" focusable="false">
          <circle className="thinking-orbit-track" cx="22" cy="22" r="16" />
          <g className="thinking-orbit-particles">
            <circle className="thinking-particle thinking-particle-primary" cx="22" cy="6" r="3.2" />
            <circle className="thinking-particle thinking-particle-secondary" cx="22" cy="38" r="2.4" />
          </g>
          <circle className="thinking-mark-center" cx="22" cy="22" r="10" />
          <g className="thinking-mark-stage">
            <path d="m17 27 2-1 9-9-2-2-9 9-1 4z" />
          </g>
        </svg>
      </span>
      <span className="thinking-copy">
        <strong>{title}</strong>
        <span className="thinking-status">{message}</span>
        <span className="thinking-elapsed" aria-hidden="true">{Math.floor(seconds)}s elapsed</span>
      </span>
      {fullScreen && <p className="generation-status-hint">Please keep this page open. Your result will appear when it’s ready.</p>}
    </div>
  );
  return fullScreen ? createPortal(
    <div className="generation-overlay" role="status" aria-label={ariaLabel || `${title}: ${message}`}>
      {content}
    </div>,
    document.body,
  ) : content;
}
