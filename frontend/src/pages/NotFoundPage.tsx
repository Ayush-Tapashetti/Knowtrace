import { Link } from "react-router-dom";

import { PageHeader } from "../components/layout/PageHeader";
import { EmptyState } from "../components/ui/states";

export function NotFoundPage() {
  return (
    <>
      <PageHeader title="Page not found" />
      <EmptyState
        title="There's nothing at this address"
        description="Check the link, or go back to practice."
        action={
          <Link
            to="/"
            className="inline-flex min-h-10 items-center rounded-control bg-ink px-4 text-sm font-medium text-paper"
          >
            Go to Practice
          </Link>
        }
      />
    </>
  );
}
