import { useState } from "react";

import { useStatus } from "../../api/hooks";
import type { Api } from "../../api/endpoints";
import { useOnlineStatus } from "../../lib/useOnlineStatus";
import { Banner } from "../ui/Banner";
import { Button } from "../ui/Button";
import { describeBackend } from "./backendState";

/** Backend and connectivity problems, plus a dismissible note when the optional model is on. */
export function StatusBanner({ client }: { client?: Api }) {
  const online = useOnlineStatus();
  const q = useStatus({ client });
  const [modelNoteDismissed, setModelNoteDismissed] = useState(false);
  const state = describeBackend({
    online,
    isPending: q.isPending,
    data: q.data,
    error: q.error,
  });

  if (state.banner) {
    const { tone, title, body, retry } = state.banner;
    return (
      <Banner
        tone={tone}
        title={title}
        fullBleed
        actions={
          retry ? (
            <Button
              variant="secondary"
              onClick={() => {
                void q.refetch();
              }}
              pending={q.isFetching}
            >
              Try again
            </Button>
          ) : null
        }
      >
        {body}
      </Banner>
    );
  }
  if (q.data?.llm_mode === "model" && !modelNoteDismissed) {
    return (
      <Banner
        tone="info"
        fullBleed
        title="AI rewording is on"
        onDismiss={() => {
          setModelNoteDismissed(true);
        }}
      >
        Lesson wording may be rewritten by a language model and is checked
        against the lesson&apos;s concepts. Which concept you are missing is
        always worked out by code.
      </Banner>
    );
  }
  return null;
}
