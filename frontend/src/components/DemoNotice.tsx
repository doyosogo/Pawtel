import { usePublicConfig } from '../features/auth/publicConfig';
export function DemoNotice() {
  const config = usePublicConfig();
  if (!config.data?.portfolio_demo) return null;
  return (
    <aside className="notice container" aria-label="Portfolio demo">
      Portfolio demo · Fictional stays and synthetic accounts only. No real
      bookings or charges. Registration and email delivery are disabled. Demo
      access is available from the project author. Use only synthetic
      information.
    </aside>
  );
}
