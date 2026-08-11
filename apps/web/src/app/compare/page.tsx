"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { DIMENSION_LABELS, HEADLINE_DIMENSIONS } from "@mirror-ops/config";
import type { SessionDetail } from "@mirror-ops/types";

import { Action } from "@/components/Action";
import { BeforeAfter } from "@/components/BeforeAfter";
import { Notice, SimulatedStamp } from "@/components/Notice";
import { Stage } from "@/components/Stage";
import { ApiError, generateVTO, getSessionDetail, listGarments, uploadGarment } from "@/lib/api";
import { actionCategory } from "@/lib/format";
import { readSessionId, stepKey } from "@/lib/session";

/**
 * Écran 06 — BEFORE / AFTER.
 *
 * Une recommandation abstraite devient une preuve. Le comparateur est le héros
 * de l'écran ; les trois lignes d'impact sont là pour expliquer le changement,
 * pas pour transformer l'écran en tableau de bord (Doc 03 §14).
 */
export default function ComparePage() {
  const router = useRouter();
  // Le chargement n'a lieu qu'une fois. Sans ce garde-fou, une référence de
  // routeur non stable relancerait l'effet à chaque rendu — donc une requête à
  // chaque rendu, indéfiniment.
  const fetched = useRef(false);
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [swapping, setSwapping] = useState(false);
  const [alternatives, setAlternatives] = useState<string[]>([]);
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
        if (!data.vto) {
          router.replace("/one-change");
          return;
        }
        setDetail(data);

        // Le document de positionnement prévoit « Keep it / Try another ».
        // « Try another » ne propose jamais un AUTRE changement : seulement une
        // autre façon d'exécuter le même. On ne charge le catalogue que pour la
        // catégorie décidée par le moteur.
        const category = data.recommendation
          ? actionCategory(data.recommendation.action)
          : null;
        if (category) {
          listGarments(category)
            .then((list) => setAlternatives(list.garments.map((g) => g.id)))
            .catch(() => setAlternatives([]));
        }
      })
      .catch((cause: unknown) =>
        setError(
          cause instanceof ApiError
            ? cause
            : new ApiError("INTERNAL_ERROR", "Something went wrong.", true, 500),
        ),
      );
  }, [router]);

  if (error && !detail) {
    return (
      <Stage step="/compare">
        <div style={{ paddingTop: "8vh" }}>
          <Notice
            title={error.message}
            actions={
              <Action variant="ghost" onClick={() => router.replace("/one-change")}>
                Back to your change
              </Action>
            }
          />
        </div>
      </Stage>
    );
  }

  const vto = detail?.vto;
  const recommendation = detail?.recommendation;

  if (!vto || !recommendation) {
    return (
      <Stage step="/compare">
        <div style={{ paddingTop: "12vh" }}>
          <p className="eyebrow">Preview</p>
          <p className="body">Bringing up your before and after.</p>
        </div>
      </Stage>
    );
  }

  const before = vto.before_image_url;
  const after = vto.result_image_url;

  // On ne propose « Try another » que s'il existe réellement une autre pièce
  // dans la catégorie décidée. Sinon le bouton mentirait.
  const canSwap = alternatives.filter((id) => id !== vto.garment_id).length > 0;

  /**
   * Essayer SA piece.
   *
   * Le catalogue sert a ce que le parcours ne s'arrete jamais ; celui qui
   * hesite devant une veste precise, lui, veut voir CELLE-LA.
   */
  async function useOwnPiece(file: File | undefined) {
    const sessionId = readSessionId();
    if (!file || !sessionId) return;

    setSwapping(true);
    setError(null);
    try {
      const uploaded = await uploadGarment({ sessionId, photo: file });
      await generateVTO({
        sessionId,
        garmentAssetId: uploaded.id,
        idempotencyKey: stepKey(sessionId, `vto:${uploaded.id}`),
      });
      setDetail(await getSessionDetail(sessionId));
    } catch (cause) {
      setError(
        cause instanceof ApiError
          ? cause
          : new ApiError("VTO_FAILED", "We couldn't build that preview.", true, 502),
      );
    } finally {
      setSwapping(false);
    }
  }

  async function tryAnother() {
    const sessionId = readSessionId();
    if (!sessionId || !vto) return;

    const next = alternatives.find((id) => id !== vto.garment_id);
    if (!next) return;

    setSwapping(true);
    setError(null);
    try {
      // La clé d'idempotence inclut le vêtement : réessayer une même pièce ne
      // consomme rien, changer de pièce consomme un aperçu — à la demande
      // explicite de l'utilisateur, jamais automatiquement.
      await generateVTO({
        sessionId,
        garmentAssetId: next,
        idempotencyKey: stepKey(sessionId, `vto:${next}`),
      });
      const refreshed = await getSessionDetail(sessionId);
      setDetail(refreshed);
    } catch (cause) {
      setError(
        cause instanceof ApiError
          ? cause
          : new ApiError("VTO_FAILED", "We couldn't build that preview.", true, 502),
      );
    } finally {
      setSwapping(false);
    }
  }

  return (
    <Stage step="/compare" wide>
      <div className="split">
        <div className="enter enter--1">
          <p className="eyebrow eyebrow--signal">See the difference</p>
          <h1 className="heading" style={{ marginBottom: 18 }}>
            {recommendation.what}
          </h1>

          {before && after ? (
            <BeforeAfter beforeUrl={before} afterUrl={after} />
          ) : (
            <Notice title="We couldn't complete the visual preview.">
              The change above still stands — you can act on it without the preview.
            </Notice>
          )}

          {vto.simulated ? (
            <div style={{ marginTop: 12 }}>
              <SimulatedStamp />
            </div>
          ) : null}
        </div>

        <div className="enter enter--2">
          <ul className="deltas" aria-label="What this change moves">
            {HEADLINE_DIMENSIONS.map((key) => {
              const from = recommendation.impact.before[key];
              const to = recommendation.impact.after[key];
              if (from === undefined || to === undefined) return null;
              return (
                <li key={key} className="deltas__row">
                  <span className="deltas__name">{DIMENSION_LABELS[key] ?? key}</span>
                  <span className="deltas__value">
                    {from}
                    <span className="deltas__arrow" aria-label="becomes">
                      →
                    </span>
                    <span className="deltas__after">{to}</span>
                  </span>
                </li>
              );
            })}
          </ul>

          <div className="stage__foot">
            {error ? (
              <Notice title={error.message}>
                The change above still stands — the preview you can see is unchanged.
              </Notice>
            ) : null}
            <Action onClick={() => router.push("/ready")}>Keep it</Action>
            {canSwap ? (
              <Action variant="ghost" onClick={tryAnother} disabled={swapping}>
                {swapping ? "Trying another…" : "Try another"}
              </Action>
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
              disabled={swapping}
            >
              Try a piece of your own
            </Action>
            <Action variant="quiet" onClick={() => router.replace("/one-change")}>
              Back to the decision
            </Action>
            <p className="fine">
              One thing moved. Everything else in your look stayed exactly as it was.
              {canSwap ? " “Try another” swaps the piece, not the decision." : ""}{" "}
              Got a specific jacket in mind? Photograph it and see it on you — the decision
              stays the same either way.
            </p>
          </div>
        </div>
      </div>
    </Stage>
  );
}
