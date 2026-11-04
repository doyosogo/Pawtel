import { useEffect, useState } from 'react';
export function useDeadline(deadline: string | null) {
  const [now, setNow] = useState(Date.now);
  const end = deadline ? Date.parse(deadline) : NaN;
  useEffect(() => {
    if (!Number.isFinite(end)) return;
    // A single expiry timer, not polling. Long deadlines are safely bounded.
    const timer = window.setTimeout(
      () => setNow(Date.now()),
      Math.min(Math.max(0, end - Date.now()) + 1, 2_147_483_647),
    );
    return () => window.clearTimeout(timer);
  }, [end]);
  return !Number.isFinite(end) || end <= now;
}
