import { useStatus } from "../../api/hooks";
import type { Api } from "../../api/endpoints";
import { cn } from "../../lib/cn";
import { useOnlineStatus } from "../../lib/useOnlineStatus";
import { describeBackend } from "./backendState";

/** Small header indicator; the text is the signal, the dot only decorates it. */
export function StatusPill({ client }: { client?: Api }) {
  const online = useOnlineStatus();
  const q = useStatus({ client });
  const { kind, pill } = describeBackend({
    online,
    isPending: q.isPending,
    data: q.data,
    error: q.error,
  });
  const dot =
    kind === "ready"
      ? "bg-known"
      : kind === "checking"
        ? "bg-ink-soft"
        : "bg-danger";
  return (
    <p className="flex items-center gap-2 text-sm text-ink-soft">
      <span aria-hidden className={cn("size-2 rounded-full", dot)} />
      {pill}
    </p>
  );
}
