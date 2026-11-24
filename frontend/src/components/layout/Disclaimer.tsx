import { useFallbackInfo } from "../../api/hooks";
import type { Api } from "../../api/endpoints";

/** Rendered by the shell so no page can leave it out. */
export function Disclaimer({ client }: { client?: Api }) {
  const info = useFallbackInfo({ client });
  const modelOn = info.status === "success" && !info.deterministic;
  return (
    <footer className="mt-12 border-t border-line py-6 text-sm text-ink-soft">
      <div className="mx-auto max-w-5xl space-y-1 px-4 sm:px-6">
        <p className="max-w-prose">
          This is a demo with sample practice content. Progress is saved under a
          random pseudonym, never a real name or roll number, and there are no
          accounts.
        </p>
        <p className="max-w-prose">
          {modelOn
            ? "Lesson wording may be rewritten by a language model. The diagnosis and the choice of lesson are always computed by code."
            : "Lesson text is written by hand. The diagnosis and the choice of lesson are computed by code, with no AI model involved."}
        </p>
      </div>
    </footer>
  );
}
