import { Link, Outlet } from "react-router-dom";

import type { Api } from "../../api/endpoints";
import { BrandMark } from "./BrandMark";
import { Disclaimer } from "./Disclaimer";
import { TopNav, TabBar } from "./Nav";
import { StatusBanner } from "./StatusBanner";
import { StatusPill } from "./StatusPill";

/** Landmarks, navigation, status and the persistent disclaimer. Pages render inside `<Outlet />`. */
export function AppShell({ client }: { client?: Api }) {
  return (
    <div className="flex min-h-dvh flex-col pb-14 md:pb-0">
      <a href="#main" className="skip-link">
        Skip to main content
      </a>
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-x-6 gap-y-1 px-4 pt-3 sm:px-6 md:pb-0">
          <Link
            to="/"
            aria-label="KnowTrace home"
            className="rounded-control py-1"
          >
            <BrandMark />
          </Link>
          <TopNav />
          <StatusPill client={client} />
        </div>
      </header>
      <StatusBanner client={client} />
      <main
        id="main"
        tabIndex={-1}
        className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 outline-none sm:px-6"
      >
        <Outlet />
      </main>
      <Disclaimer client={client} />
      <TabBar />
    </div>
  );
}
