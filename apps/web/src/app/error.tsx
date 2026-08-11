"use client";

import { useEffect } from "react";

/**
 * Dernier filet de sécurité de l'interface. On n'affiche jamais la pile
 * d'appels : on dit ce qui s'est passé et ce qu'il faut faire ensuite.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="stage">
      <main className="stage__body" style={{ paddingTop: "14vh" }}>
        <p className="eyebrow">Interrupted</p>
        <h1 className="heading">Mirror Ops stopped mid-flow.</h1>
        <p className="body">Nothing was saved to your name — there isn&apos;t one.</p>
        <div className="spacer" />
        <div className="stage__foot">
          <button type="button" className="action" onClick={reset}>
            Try again
          </button>
        </div>
      </main>
    </div>
  );
}
