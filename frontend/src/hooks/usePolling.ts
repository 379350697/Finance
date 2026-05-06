import { useEffect, useRef, useState } from "react";

export function usePolling<T>(
  fetcher: () => Promise<T>,
  intervalMs: number,
  enabled = true,
): T | undefined {
  const [data, setData] = useState<T>();
  const savedFetcher = useRef(fetcher);
  savedFetcher.current = fetcher;

  useEffect(() => {
    if (!enabled) return;
    let active = true;

    const poll = async () => {
      while (active) {
        try {
          const result = await savedFetcher.current();
          if (active) setData(result);
        } catch {
          // silent fail, keep last good value
        }
        await new Promise((r) => setTimeout(r, intervalMs));
      }
    };
    poll();

    return () => {
      active = false;
    };
  }, [intervalMs, enabled]);

  return data;
}
