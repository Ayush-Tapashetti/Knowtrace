import { Network, Pencil, FlaskConical, type LucideIcon } from "lucide-react";

/** Placeholder product name (Step 1); change it here only. */
export const APP_NAME = "KnowTrace";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  /** Match the path exactly (the home route). */
  end?: boolean;
}

/** The three P0-facing screens: answer questions, see the knowledge state, see the evidence. */
export const NAV_ITEMS: readonly NavItem[] = [
  { to: "/", label: "Practice", icon: Pencil, end: true },
  { to: "/map", label: "Knowledge map", icon: Network },
  { to: "/evaluation", label: "Evaluation", icon: FlaskConical },
];
