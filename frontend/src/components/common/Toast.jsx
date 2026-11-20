import React, { createContext, useContext, useState, useCallback, useRef, useEffect } from "react";
import "./Toast.css";

const ToastContext = createContext(null);

let toastSeq = 0;

/**
 * Shared Toast Notification Provider
 *
 * Provides a centralized notification mechanism across the WorkSphere frontend.
 *
 * Usage Example:
 * ```jsx
 * import { useToast } from "../components/common/Toast";
 *
 * function MyComponent() {
 *   const toast = useToast();
 *
 *   const handleSubmit = async () => {
 *     try {
 *       await api.submit();
 *       toast.success("Action completed successfully!");
 *     } catch (err) {
 *       toast.error(err.message || "Failed to complete action.");
 *     }
 *   };
 * }
 * ```
 */
export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const timersRef = useRef(new Map());

  const dismiss = useCallback((id) => {
    if (timersRef.current.has(id)) {
      clearTimeout(timersRef.current.get(id));
      timersRef.current.delete(id);
    }
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const show = useCallback(
    ({ type = "info", message, title = "", duration }) => {
      const id = ++toastSeq;
      const defaultDuration = type === "error" ? 6000 : 4000;
      const effectiveDuration = duration !== undefined ? duration : defaultDuration;

      const newToast = {
        id,
        type,
        message,
        title,
        duration: effectiveDuration,
      };

      setToasts((prev) => [...prev, newToast]);

      if (effectiveDuration > 0) {
        const timerId = setTimeout(() => {
          dismiss(id);
        }, effectiveDuration);
        timersRef.current.set(id, timerId);
      }

      return id;
    },
    [dismiss]
  );

  const success = useCallback(
    (message, title = "") => show({ type: "success", message, title }),
    [show]
  );

  const error = useCallback(
    (message, title = "") => show({ type: "error", message, title }),
    [show]
  );

  const info = useCallback(
    (message, title = "") => show({ type: "info", message, title }),
    [show]
  );

  // Clean up all pending timers on unmount
  useEffect(() => {
    const timers = timersRef.current;
    return () => {
      timers.forEach((timerId) => clearTimeout(timerId));
      timers.clear();
    };
  }, []);

  return (
    <ToastContext.Provider value={{ show, success, error, info, dismiss }}>
      {children}
      <div
        className="wms-toast-container"
        aria-live="polite"
        aria-atomic="false"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`wms-toast wms-toast-${t.type}`}
            role={t.type === "error" ? "alert" : "status"}
          >
            <span className="wms-toast-icon" aria-hidden="true">
              {t.type === "success" && "✓"}
              {t.type === "error" && "⚠"}
              {t.type === "info" && "ℹ"}
            </span>
            <div className="wms-toast-content">
              {t.title && <div className="wms-toast-title">{t.title}</div>}
              <div className="wms-toast-message">{t.message}</div>
            </div>
            <button
              type="button"
              className="wms-toast-close"
              onClick={() => dismiss(t.id)}
              aria-label="Dismiss notification"
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

/**
 * Hook to access the shared Toast notification API.
 * @returns {{
 *   show: (opts: { type: 'success'|'error'|'info', message: string, title?: string, duration?: number }) => number,
 *   success: (message: string, title?: string) => number,
 *   error: (message: string, title?: string) => number,
 *   info: (message: string, title?: string) => number,
 *   dismiss: (id: number) => void
 * }}
 */
export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return context;
}

export default ToastProvider;
