import { NavLink } from "react-router-dom";

import { NAV_ITEMS } from "../../lib/brand";
import { cn } from "../../lib/cn";

/** Top navigation on wide screens. The marigold bar under the current page is the "highlighter". */
export function TopNav() {
  return (
    <nav aria-label="Primary" className="hidden md:block">
      <ul className="flex gap-1">
        {NAV_ITEMS.map(({ to, label, end }) => (
          <li key={to}>
            <NavLink
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  "block border-b-[3px] px-3 py-2 text-[0.95rem] font-medium transition-colors",
                  isActive
                    ? "border-gap"
                    : "border-transparent text-ink-soft hover:text-ink",
                )
              }
            >
              {label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}

/** Bottom tab bar on phones, where thumbs reach. */
export function TabBar() {
  return (
    <nav
      aria-label="Primary"
      className="fixed inset-x-0 bottom-0 z-20 border-t border-line bg-surface pb-[env(safe-area-inset-bottom)] md:hidden"
    >
      <ul className="grid grid-cols-3">
        {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
          <li key={to}>
            <NavLink
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  "flex min-h-14 flex-col items-center justify-center gap-0.5 border-t-[3px] text-xs font-medium",
                  isActive
                    ? "border-gap text-ink"
                    : "border-transparent text-ink-soft",
                )
              }
            >
              <Icon aria-hidden className="size-5" />
              {label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
