import { useEffect, type ReactNode } from "react";

import { APP_NAME } from "../../lib/brand";

/** Page title (the one `h1`) with a one-line purpose. Also sets the tab title. */
export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  useEffect(() => {
    document.title = `${title} | ${APP_NAME}`;
  }, [title]);
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1>{title}</h1>
        {description ? (
          <p className="mt-1 max-w-prose text-ink-soft">{description}</p>
        ) : null}
      </div>
      {actions}
    </div>
  );
}
