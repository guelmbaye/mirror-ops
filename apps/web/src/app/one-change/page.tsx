"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import type { SessionDetail } from "@mirror-ops/types";

import { Action } from "@/components/Action";
import { Notice } from "@/components/Notice";
import { Stage } from "@/components/Stage";
import { Verdict } from "@/components/Verdict";
import { ApiError, generateVTO, getSessionDetail, uploadGarment } from "@/lib/api";
import { readSessionId, stepKey } from "@/lib/session";

/**
 * Écran 05 — ONE CHANGE.
 *
 * L'écran signature. La décision est relue depuis l'API plutôt que transportée
 * d'un écran à l'autre : un rafraîchissement retrouve exactement la même
 * recommandation, ce qui compte autant pour une démo que pour la confiance.
 */
export default function OneChangePage() {
  const router = useRouter();
  // Le chargement n'a lieu qu'une fois. Sans ce garde-fou, une référence de
  // routeur non stable relancerait l'effet à chaque rendu — donc une requête à
  // chaque rendu, indéfiniment.
  const fetched = useRef(false);
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [generating, setGenerating] = useState(false);
  const garmentInput = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (fetched.current) return;
    fetched.current = true;

    const sessionId = readSessionId();
    if (!sessionId) {
      router.replace("/");
      return;
    }
    getSessionDetail(sessionId)
      .then((data) => {
        if (!data.recommendation) {
          router.replace("/look");
          return;
        }
        setDetail(data);
      })
      .catch((cause: unknown) => {
        if (cause instanceof ApiError && cause.code === "NOT_FOUND") {
          router.replace("/");
          return;
        }
        setError(
          cause instanceof ApiError
            ? cause
            : new ApiError("INTERNAL_ERROR", "Something went wrong.", true, 500),
        );
      });
  }, [router]);

  /**
   * Essayer SA piece, depuis l'ecran de decision.
   *
   * Ce bouton vivait uniquement sur l'ecran Before/After — donc derriere un
   * essayage reussi. Quand le catalogue echoue, c'est precisement ici que la
   * personne se trouve : l'echappatoire doit etre du bon cote de la porte.
   */
  async function useOwnPiece(file: File | undefined) {
    const sessionId = readSessionId();
    if (!file || !sessionId) return;

    setGenerating(true);
    setError(null);
    try {
      const uploaded = await uploadGarment({ sessionId, photo: file });
      await generateVTO({
        sessionId,
        garmentAssetId: uploaded.id,
        idempotencyKey: stepKey(sessionId, `vto:${uploaded.id}`),
      });
      router.push("/compare");
    } catch (cause) {
      setError(
        cause instanceof ApiError
          ? cause
          : new ApiError("VTO_FAILED", "We couldn't build that preview.", true, 502),
      );
      setGenerating(false);
    }
  }

  async function seeTheDifference() {
    const sessionId = readSessionId();
    if (!sessionId) return;
    setGenerating(true);
    setError(null);
    try {
      await generateVTO({ sessionId, idempotencyKey: stepKey(sessionId, "vto") });
      router.push("/compare");
    } catch (cause) {
      setError(
        cause instanceof ApiError
          ? cause
          : new ApiError("VTO_FAILED", "We couldn't complete the visual preview.", true, 502),
      );
      setGenerating(false);
    }
  }

  if (error && !detail) {
    return (
      <Stage step="/one-change">
        <div style={{ paddingTop: "8vh" }}>
          <Notice
            title={error.message}
            actions={<Action onClick={() => window.location.reload()}>Try again</Action>}
          />
        </div>
      </Stage>
    );
  }

  if (!detail?.recommendation) {
    return (
      <Stage step="/one-change">
        <div style={{ paddingTop: "12vh" }}>
          <p className="eyebrow">Deciding</p>
          <p className="body">Bringing up your one change.</p>
        </div>
      </Stage>
    );
  }

  const recommendation = detail.recommendation;
  const hold = recommendation.action === "NO_CHANGE";
  const photo = detail.analysis?.image_url ?? null;

  return (
    <Stage step="/one-change" wide back="/look">
      <div className="split">
        {/* Sur desktop, la photo tient la moitié gauche ; sur mobile elle passe
            après la décision, qui doit rester la première chose lue. */}
        {photo ? (
          <div className="enter enter--2" style={{ order: 2 }}>
            <div className="capture capture--filled">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img className="capture__img" src={photo} alt="Your current look" />
            </div>
          </div>
        ) : null}

        <div className="enter enter--1" style={{ order: 1 }}>
          <Verdict recommendation={recommendation} />

          <div className="stage__foot">
            {error ? (
              <Notice title={error.message}>
                {error.retryable
                  ? "You can try again with a piece of your own — photograph the jacket you have in mind and see it on you. The decision above doesn't change either way."
                  : "The decision above still stands."}
              </Notice>
            ) : null}

            {/* Un retrait ne se prouve pas : il n'y a rien a essayer. */}
            {hold || !recommendation.requires_vto ? (
              <>
                <Action onClick={() => router.push("/ready")}>
                  {hold ? "You're good to go" : "Done"}
                </Action>
                <p className="fine">
                  {hold
                    ? "Nothing to preview, so no try-on is generated. Your look already fits the moment you're about to enter."
                    : "Nothing to try on here — this one is a subtraction. No preview needed."}
                </p>
              </>
            ) : (
              <>
                {/* Deux chemins vers la même preuve. Le premier annonce la
                    pièce retenue — informer, sans offrir un catalogue à
                    parcourir. Le second dit qu'il attend une photo. */}
                <Action onClick={seeTheDifference} disabled={generating}>
                  {generating ? "Preparing your preview… (~15s)" : "See the difference"}
                </Action>
                {recommendation.suggested_garment ? (
                  <p className="path-hint">
                    We&apos;ll use our{" "}
                    <strong>{recommendation.suggested_garment.name}</strong> to show you.
                  </p>
                ) : null}
                <input
                  ref={garmentInput}
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  className="sr-only"
                  onChange={(event) => void useOwnPiece(event.target.files?.[0])}
                />
                <Action
                  variant="ghost"
                  onClick={() => garmentInput.current?.click()}
                  disabled={generating}
                >
                  Try a piece of your own
                </Action>
                <p className="path-hint">
                  Photograph the one you&apos;re considering, and see it on you instead.
                </p>
                <Action variant="quiet" onClick={() => router.push("/ready")}>
                  Skip the preview
                </Action>
                <p className="fine">
                  Decision confidence: {recommendation.confidence} · impact{" "}
                  {Math.round(recommendation.score)}/100. Scores explain the change; they
                  don&apos;t claim to measure how you&apos;ll feel.
                </p>
              </>
            )}
          </div>
        </div>
      </div>
    </Stage>
  );
}
