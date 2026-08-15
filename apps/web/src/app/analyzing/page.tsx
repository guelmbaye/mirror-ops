"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Action } from "@/components/Action";
import { Notice } from "@/components/Notice";
import { Stage } from "@/components/Stage";
import {
  ApiError,
  analyzeAppearance,
  evaluateOneChange,
  getSessionDetail,
} from "@/lib/api";
import { getMoment, getOutfit, getPhoto } from "@/lib/photo";
import { fingerprint, readSessionId, stepKey } from "@/lib/session";

const STEPS = [
  "Reading your look",
  "Understanding the moment",
  "Finding the biggest opportunity",
];

/** Intervalle du filet de sécurité, et nombre de tentatives avant d'abandonner. */
const WATCHDOG_MS = 8000;
const WATCHDOG_TRIES = 4;

/**
 * Écran 04 — ANALYZING.
 *
 * L'attente devient une explication. Les appels YouCam se font côté backend :
 * l'interface n'affiche que des états lisibles (Doc 03 §9). La dernière phrase
 * prépare mentalement à la proposition centrale — une seule chose, pas dix.
 *
 * C'est le seul écran qui enchaîne deux appels asynchrones puis navigue : c'est
 * donc le seul qui peut se retrouver bloqué si une promesse ne revient jamais.
 * Il ne se contente pas de son état interne — l'état officiel est côté serveur,
 * et un filet de sécurité va le relire régulièrement pour reprendre le parcours
 * là où il en est réellement.
 */
export default function AnalyzingPage() {
  const router = useRouter();
  const started = useRef(false);
  const cancelled = useRef(false);
  const settled = useRef(false);
  const noPhoto = useRef(false);
  const [reached, setReached] = useState(0);
  const [failure, setFailure] = useState<ApiError | null>(null);
  const [lost, setLost] = useState(false);

  useEffect(() => {
    // En développement, StrictMode monte, démonte puis remonte le composant.
    // `started` empêche un second appel réseau ; `cancelled` doit donc être
    // réarmé à CHAQUE passage, avant ce garde-fou — sinon le nettoyage du
    // premier montage annule définitivement l'orchestration déjà lancée, et
    // l'écran reste figé sur la première étape alors que l'API a répondu.
    cancelled.current = false;

    if (!started.current) {
      started.current = true;
      void begin();
    }

    // Filet de sécurité : si l'orchestration ne progresse plus — promesse qui
    // ne revient jamais, onglet mis en veille, hoquet réseau — on relit l'état
    // réel de la session et on reprend là où le serveur en est. C'est un simple
    // GET : aucune unité API n'est consommée.
    let tries = 0;
    const watchdog = window.setInterval(() => {
      // Une orchestration qui a rendu son verdict — succes ou echec — n'a plus
      // rien a recuperer.
      if (settled.current || cancelled.current) {
        window.clearInterval(watchdog);
        return;
      }
      tries += 1;
      void recover(tries >= WATCHDOG_TRIES);
    }, WATCHDOG_MS);

    return () => {
      cancelled.current = true;
      window.clearInterval(watchdog);
    };

    function leave() {
      settled.current = true;
      router.replace("/one-change");
    }

    async function begin() {
      const sessionId = readSessionId();
      const photo = getPhoto();

      if (!sessionId) {
        router.replace("/");
        return;
      }
      if (!photo) {
        // Onglet rechargé : la photo ne vit qu'en mémoire, on la redemande
        // plutôt que d'analyser autre chose.
        noPhoto.current = true;
        setLost(true);
        return;
      }

      // Le fil d'étapes avance avec le travail réel, pas sur un minuteur seul :
      // il s'arrête là où l'orchestration en est.
      try {
        setReached(1);
        const outfit = getOutfit() ?? undefined;
        // La cle couvre TOUT ce dont l'analyse depend : la photo, la tenue et
        // le moment. Le moment compte parce que l'analyse evalue l'adequation
        // de chaque piece a CE moment — l'omettre figeait le resultat sur la
        // premiere occasion choisie.
        const inputs = fingerprint(
          JSON.stringify(outfit ?? {}),
          getMoment() ?? "",
          photo.file.size,
          photo.file.lastModified,
        );
        await analyzeAppearance({
          sessionId,
          photo: photo.file,
          outfit,
          idempotencyKey: stepKey(sessionId, `analyze:${inputs}`),
        });
        if (cancelled.current || settled.current) return;

        setReached(2);
        await evaluateOneChange(sessionId);
        if (cancelled.current || settled.current) return;

        setReached(3);
        window.setTimeout(() => {
          if (!cancelled.current && !settled.current) leave();
        }, 420);
      } catch (cause) {
        if (cancelled.current || settled.current) return;
        if (cause instanceof ApiError) {
          if (cause.code === "SESSION_EXPIRED") {
            router.replace("/");
            return;
          }
          // Le filet de sécurité existe pour une orchestration BLOQUÉE, pas
          // pour une qui a échoué franchement. Sans cette ligne, un refus de
          // photo laissait le watchdog interroger le serveur toutes les huit
          // secondes, indéfiniment — observé sur deux minutes en production —
          // pendant que l'utilisateur regardait un écran figé.
          settled.current = true;
          setFailure(cause);
        } else {
          settled.current = true;
          setFailure(
            new ApiError("INTERNAL_ERROR", "Something went wrong on our side.", true, 500),
          );
        }
      }
    }

    /**
     * Reprend le parcours depuis l'état officiel.
     *
     * @param last dernière tentative : au-delà, mieux vaut dire à l'utilisateur
     *             que ça n'avance pas plutôt que de le laisser devant une
     *             animation qui tourne indéfiniment.
     */
    async function recover(last: boolean) {
      if (cancelled.current || settled.current || noPhoto.current) return;

      const sessionId = readSessionId();
      if (!sessionId) return;

      try {
        const detail = await getSessionDetail(sessionId);
        if (cancelled.current || settled.current) return;

        // La décision existe déjà : on y va.
        if (detail.recommendation) {
          setReached(3);
          leave();
          return;
        }

        // L'analyse est passée mais la décision manque : on la demande.
        if (detail.analysis) {
          setReached(2);
          await evaluateOneChange(sessionId);
          if (cancelled.current || settled.current) return;
          setReached(3);
          leave();
          return;
        }

        // Rien côté serveur : l'analyse est peut-être encore en cours.
        if (last) {
          setFailure(
            new ApiError(
              "ANALYSIS_FAILED",
              "This is taking longer than it should.",
              true,
              504,
            ),
          );
        }
      } catch (cause) {
        if (cancelled.current || settled.current || !last) return;
        setFailure(
          cause instanceof ApiError
            ? cause
            : new ApiError("INTERNAL_ERROR", "Something went wrong on our side.", true, 500),
        );
      }
    }
  }, [router]);

  if (lost) {
    return (
      <Stage step="/look">
        <div className="enter enter--1" style={{ paddingTop: "8vh" }}>
          <Notice
            title="We need your photo again."
            actions={<Action onClick={() => router.replace("/look")}>Back to your look</Action>}
          >
            Photos are held in memory for the length of a single flow, so reloading the page
            clears them.
          </Notice>
        </div>
      </Stage>
    );
  }

  if (failure) {
    return (
      <Stage step="/look">
        <div className="enter enter--1" style={{ paddingTop: "8vh" }}>
          <Notice
            title={failure.message}
            actions={
              <>
                {failure.retryable ? (
                  <Action onClick={() => window.location.reload()}>Try again</Action>
                ) : null}
                <Action variant="ghost" onClick={() => router.replace("/look")}>
                  Retake photo
                </Action>
              </>
            }
          >
            {failure.code === "INVALID_IMAGE"
              ? "A clearer, better-lit shot usually fixes this."
              : "Nothing has been decided yet — your moment is still saved."}
          </Notice>
        </div>
      </Stage>
    );
  }

  return (
    <Stage step="/look">
      <div className="enter enter--1" style={{ paddingTop: "10vh" }}>
        <p className="eyebrow">Working</p>
        <ol className="steps">
          {STEPS.map((label, index) => (
            <li
              key={label}
              className={
                index < reached - 1
                  ? "steps__item steps__item--done"
                  : index === reached - 1
                    ? "steps__item steps__item--active"
                    : "steps__item"
              }
            >
              <span className="steps__dot" aria-hidden="true" />
              {label}
            </li>
          ))}
        </ol>
      </div>

      <div className="spacer" />

      <div className="stage__foot enter enter--2">
        <p className="body body--ink" style={{ fontSize: 17 }}>
          We&apos;re looking for one change — not ten.
        </p>
      </div>
    </Stage>
  );
}
