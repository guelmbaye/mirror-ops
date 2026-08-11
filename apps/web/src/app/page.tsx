"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { PRODUCT } from "@mirror-ops/config";

import { Action } from "@/components/Action";
import { Notice } from "@/components/Notice";
import { Stage } from "@/components/Stage";
import { ApiError, createSession } from "@/lib/api";
import { clearPhoto } from "@/lib/photo";
import { saveSessionId } from "@/lib/session";

/**
 * Écran 01 — HOME.
 *
 * Une thèse, un chemin, un bouton. Pas de tableau de bord, pas d'historique,
 * pas d'onboarding (Doc 03 §4). En moins de quinze secondes, on doit comprendre
 * ce que fait le produit et quoi faire ensuite.
 */
export default function HomePage() {
  const router = useRouter();
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function start() {
    setStarting(true);
    setError(null);
    clearPhoto();
    try {
      const session = await createSession();
      saveSessionId(session.id);
      router.push("/moment");
    } catch (cause) {
      setError(
        cause instanceof ApiError ? cause.message : "We can't reach Mirror Ops right now.",
      );
      setStarting(false);
    }
  }

  return (
    <Stage bare>
      <div className="stack enter enter--1" style={{ paddingTop: "8vh" }}>
        <span className="wordmark wordmark--hero" style={{ marginBottom: 26 }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo-mirror-ops@2x.png" alt="Mirror Ops" width={146} height={44} />
        </span>
        <p className="eyebrow">{PRODUCT.category}</p>
        <h1 className="display">
          Fit the moment.
          <br />
          <span style={{ color: "var(--signal)" }}>One change.</span>
        </h1>
        <p className="body body--ink" style={{ maxWidth: "32ch", fontSize: 18 }}>
          {PRODUCT.promise}
        </p>
        <p className="body" style={{ maxWidth: "36ch", marginTop: 14 }}>
          The same outfit can be right for a dinner and wrong for a wedding. Mirror Ops
          answers one question — <em>{PRODUCT.question}</em> — and when the answer is no, it
          names the single change worth making and shows you the difference first.
        </p>
      </div>

      <div className="spacer" />

      <ul className="pathline enter enter--2" aria-label="How it works">
        <li>Moment</li>
        <li>Current look</li>
        <li>Fit or mismatch</li>
        <li>One change</li>
        <li>Proof</li>
      </ul>

      <div className="stage__foot enter enter--3">
        {error ? (
          <Notice title={error}>
            Check that the Mirror Ops API is running, then start again.
          </Notice>
        ) : null}
        <Action onClick={start} disabled={starting}>
          {starting ? "Starting…" : "Start Mirror Ops"}
        </Action>
        <p className="fine">
          No account. Your photo is kept only for this session, then deleted.
        </p>
      </div>
    </Stage>
  );
}
