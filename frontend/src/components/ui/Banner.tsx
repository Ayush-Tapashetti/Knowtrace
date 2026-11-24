import {
  CircleAlert,
  CircleCheck,
  Info,
  TriangleAlert,
  X,
  type LucideIcon,
} from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "../../lib/cn";

export type BannerTone = "info" | "success" | "warning" | "error";

const STYLE: Record<BannerTone, { box: string; icon: LucideIcon }> = {
  info: { box: "border-ink/20 bg-info-tint", icon: Info },
  success: { box: "border-known/40 bg-known-tint", icon: CircleCheck },
  warning: { box: "border-gap bg-gap-tint", icon: TriangleAlert },
  error: { box: "border-danger/50 bg-danger-tint", icon: CircleAlert },
};

export interface BannerProps {
  tone?: BannerTone;
  title?: string;
  children?: ReactNode;
  /** Buttons such as "Try again". */
  actions?: ReactNode;
  /** Only pass this for banners that are safe to hide (informational ones). */
  onDismiss?: () => void;
  className?: string;
  /** Edge-to-edge strip whose content lines up with the page column (used by the shell). */
  fullBleed?: boolean;
}

/** Errors are announced immediately (`alert`); everything else politely (`status`). */
export function Banner({
  tone = "info",
  title,
  children,
  actions,
  onDismiss,
  className,
  fullBleed = false,
}: BannerProps) {
  const { box, icon: Icon } = STYLE[tone];
  const content = (
    <div
      className={cn(
        "flex gap-3",
        fullBleed && "mx-auto max-w-5xl px-4 py-3 sm:px-6",
      )}
    >
      <Icon aria-hidden className="mt-0.5 size-5 shrink-0" />
      <div className="min-w-0 flex-1">
        {title ? <p className="font-semibold">{title}</p> : null}
        {children ? <div className="max-w-prose">{children}</div> : null}
        {actions ? (
          <div className="mt-2 flex flex-wrap gap-2">{actions}</div>
        ) : null}
      </div>
      {onDismiss ? (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss"
          className="-m-1 h-8 w-8 shrink-0 rounded-control p-1 hover:bg-ink/10"
        >
          <X aria-hidden className="mx-auto size-4" />
        </button>
      ) : null}
    </div>
  );
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={cn(
        "text-sm",
        fullBleed ? "border-b-2" : "border-l-4 px-4 py-3",
        box,
        className,
      )}
    >
      {content}
    </div>
  );
}
