import Link from "next/link";
import type { ReactNode } from "react";

import { FLOW_STEPS } from "@mirror-ops/config";

interface StageProps {
  /** Étape courante du parcours, ou `null` sur les écrans hors parcours. */
  step?: (typeof FLOW_STEPS)[number]["path"] | null;
  wide?: boolean;
  /** L'accueil affiche le logo en grand dans son contenu : l'en-tête s'efface. */
  bare?: boolean;
  /** Écran précédent. Sans lui, une occasion mal choisie oblige à tout refaire. */
  back?: string;
  children: ReactNode;
}

/**
 * Le plateau commun à tous les écrans.
 *
 * Un seul en-tête, un seul fil d'étapes, une colonne étroite : le parcours doit
 * ressembler à une suite de décisions, pas à une application à onglets.
 */
export function Stage({ step = null, wide = false, bare = false, back, children }: StageProps) {
  if (bare) {
    return <div className={wide ? "stage stage--wide" : "stage"}>{children}</div>;
  }

  return (
    <div className={wide ? "stage stage--wide" : "stage"}>
      <header className="stage__head">
        {back ? (
          <Link href={back} className="stage__back" aria-label="Go back one step">
            ←
          </Link>
        ) : null}
        <Link href="/" className="wordmark" aria-label="Mirror Ops — home">
          {/* Fichier 2x servi à 26 px de haut : net sur écran dense, et pas de
              next/image ici — l'asset est local, connu, et déjà dimensionné. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/logo-mirror-ops.png"
            alt="Mirror Ops"
            width={86}
            height={26}
            className="wordmark__img"
          />
        </Link>
        {step ? <StepRail current={step} /> : null}
      </header>
      <main className="stage__body">{children}</main>
    </div>
  );
}

function StepRail({ current }: { current: string }) {
  const index = FLOW_STEPS.findIndex((s) => s.path === current);
  const label = index >= 0 ? FLOW_STEPS[index].label : "";

  return (
    <div className="rail" aria-label={`Step ${index + 1} of ${FLOW_STEPS.length}: ${label}`}>
      {FLOW_STEPS.map((s, i) => (
        <span
          key={s.path}
          aria-hidden="true"
          className={
            i < index
              ? "rail__seg rail__seg--done"
              : i === index
                ? "rail__seg rail__seg--here"
                : "rail__seg"
          }
        />
      ))}
      <span className="rail__label" aria-hidden="true">
        {label}
      </span>
    </div>
  );
}
