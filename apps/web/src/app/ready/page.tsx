"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { ELEMENT_LABELS } from "@mirror-ops/config";
import type { SessionDetail } from "@mirror-ops/types";

import { Action } from "@/components/Action";
import { Stage } from "@/components/Stage";
import { getSessionDetail } from "@/lib/api";
import { actionElement } from "@/lib/format";
import { clearPhoto } from "@/lib/photo";
import { clearSession, readSessionId } from "@/lib/session";

/**
 * Écran 07 — READY.
 *
 * Conclure vite (Doc 03 §15). Une phrase, le récapitulatif de ce qui a changé
 * et de ce qui est resté, et la sortie.
 */
export default function ReadyPage() {
  const router = useRouter();
  // Le chargement n'a lieu qu'une fois. Sans ce garde-fou, une référence de
  // routeur non stable relancerait l'effet à chaque rendu — donc une requête à
  // chaque rendu, indéfiniment.
  const fetched = useRef(false);
  const [detail, setDetail] = useState<SessionDetail | null>(null);

  useEffect(() => {
    if (fetched.current) return;
    fetched.current = true;

    const sessionId = readSessionId();
    if (!sessionId) {
      router.replace("/");
      return;
    }
    getSessionDetail(sessionId)
      .then(setDetail)
      .catch(() => setDetail(null));
  }, [router]);

  function startOver() {
    clearPhoto();
    clearSession();
    router.push("/");
  }

  const recommendation = detail?.recommendation;
  const changed = recommendation ? actionElement(recommendation.action) : null;
  const held = recommendation?.action === "NO_CHANGE";

  return (
    <Stage>
      <div className="enter enter--1" style={{ paddingTop: "12vh" }}>
        <p className="eyebrow eyebrow--signal">Ready</p>
        <h1 className="display">
          {held ? (
            <>
              You&apos;re ready.
              <br />
              Nothing to change.
            </>
          ) : (
            <>
              You&apos;re ready.
            </>
          )}
        </h1>
        <p className="body body--ink" style={{ fontSize: 17 }}>
          {held
            ? recommendation?.fit?.detail ??
              "Your look already matched the moment. That's an answer too."
            : "One change. That's all you needed."}
        </p>
      </div>

      {/* Terminer sur du texte prive l'ecran final de la seule chose qui
          prouve quelque chose. On montre le resultat, et on le laisse emporter. */}
      {detail?.vto?.result_image_url ? (
        <div className="enter enter--2" style={{ marginTop: 28 }}>
          <div className="capture capture--filled">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              className="capture__img"
              src={detail.vto.result_image_url}
              alt="Your look after the change"
            />
          </div>
          {/* Nouvel onglet, et non un telechargement direct : l'attribut
              `download` est ignore par les navigateurs quand l'image vient
              d'une autre origine — l'interface est sur :3000, les medias sur
              :8000. Le lien quittait donc l'application sans rien enregistrer. */}
          <a
            className="action action--ghost"
            style={{ marginTop: 10 }}
            href={detail.vto.result_image_url}
            target="_blank"
            rel="noopener noreferrer"
            download="mirror-ops.jpg"
          >
            Save this
          </a>
          <p className="fine" style={{ marginTop: 8 }}>
            Opens in a new tab — save it from there. The link expires with your session.
          </p>
        </div>
      ) : null}

      {recommendation ? (
        <ul className="ledger enter enter--2" style={{ marginTop: 32 }}>
          {changed ? (
            <li className="ledger__row ledger__row--changed">
              <span className="ledger__verb">
                {recommendation?.is_addition ? "Added" : "Changed"}
              </span>
              <span>{ELEMENT_LABELS[changed] ?? changed}</span>
            </li>
          ) : null}
          <li className="ledger__row ledger__row--kept">
            <span className="ledger__verb">Kept</span>
            <span>{held ? "Everything" : "Everything else"}</span>
          </li>
        </ul>
      ) : null}

      <div className="spacer" />

      <div className="stage__foot enter enter--3">
        <Action onClick={startOver}>Start another moment</Action>
        <p className="fine">
          Your photo and preview are deleted when this session expires.
        </p>
      </div>
    </Stage>
  );
}
