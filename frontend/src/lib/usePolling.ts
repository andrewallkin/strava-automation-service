import { useEffect } from "react";

/**
 * Load data on mount and (optionally) re-poll on an interval.
 * The load callback must catch its own errors; pass onError to handle
 * unexpected rejections.
 */
export function usePolling(
  load: () => Promise<void>,
  intervalMs: number | null = null,
  onError?: () => void,
): void {
  useEffect(() => {
    const run = () => load().catch(onError);
    void run();
    if (intervalMs === null) return;
    const timer = window.setInterval(run, intervalMs);
    return () => window.clearInterval(timer);
  }, [load, intervalMs, onError]);
}
