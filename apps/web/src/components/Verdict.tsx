"use client";

import { useEffect, useState } from "react";

import { DIMENSION_LABELS, ELEMENT_LABELS } from "@mirror-ops/config";
import type { Recommendation } from "@mirror-ops/types";

import { actionElement } from "@/lib/format";

/**
 * L'écran signature du produit.
 *
 * Une seule recommandation, sa raison, son impact, ce qu'on garde. Pas
 * d'alternative, pas de carrousel, pas de liste de produits (Doc 03 §11).
 * La hiérarchie visuelle est elle-même l'argument : une ligne change, tout le
 * reste est explicitement conservé.
 */
export function Verdict({ recommendation }: { recommendation: Recommendation }) {
  const hold = recommendation.action === "NO_CHANGE";
  const changed = actionElement(recommendation.action);

  const fit = recommendation.fit;

  return (
    <section className={hold ? "verdict verdict--hold" : "verdict"}>
      {/* Le produit repond d'abord « ce look va-t-il ici ? », et seulement
          ensuite « que changer ? ». L'ordre est le positionnement. */}
      {fit ? (
        <div className="fitline">
          <p className={`fitline__state fitline__state--${fit.state.toLowerCase()}`}>
            {fit.headline}
          </p>
          <p className="fitline__detail">{fit.detail}</p>
          <FitGauge score={fit.score} state={fit.state} />
        </div>
      ) : null}

      <p className={hold ? "eyebrow" : "eyebrow eyebrow--signal"}>
        {hold ? "No change needed" : "One change"}
      </p>

      <h1 className="verdict__line">{recommendation.what}</h1>
      <p className="verdict__why">{recommendation.why}</p>

      <ImpactNeedle recommendation={recommendation} />

      <Ledger
        changed={changed}
        kept={recommendation.keep}
        verb={recommendation.is_addition ? "Add" : "Change"}
      />
    </section>
  );
}

/**
 * L'adequation au moment, sur le meme axe que l'impact : une graduation, pas
 * une note. Trois etats seulement — le produit tranche, il ne nuance pas.
 */
function FitGauge({ score, state }: { score: number; state: string }) {
  return (
    <div
      className="fitgauge"
      role="img"
      aria-label={`Contextual fit: ${score} out of 100`}
    >
      <span className="fitgauge__track" />
      <span
        className={`fitgauge__fill fitgauge__fill--${state.toLowerCase()}`}
        style={{ width: `${score}%` }}
      />
      <span className="fitgauge__value">{score}</span>
    </div>
  );
}

/**
 * L'aiguille d'impact — un axe, deux positions.
 *
 * Le trait fin marque l'état actuel, le trait plein l'état projeté. Un seul
 * mouvement se lit en une seconde ; c'est délibérément ni une jauge circulaire
 * ni un radar (Doc 03 §14). Les scores expliquent le changement, ils ne
 * prétendent pas mesurer scientifiquement la confiance humaine.
 */
function ImpactNeedle({ recommendation }: { recommendation: Recommendation }) {
  const key = leadDimension(recommendation);
  const before = recommendation.impact.before[key] ?? 0;
  const after = recommendation.impact.after[key] ?? before;

  // On part de la position "avant" et on laisse l'aiguille rejoindre "après" :
  // le déplacement est l'information.
  const [position, setPosition] = useState(before);
  useEffect(() => {
    const timer = window.setTimeout(() => setPosition(after), 180);
    return () => window.clearTimeout(timer);
  }, [after]);

  const low = Math.min(before, position);
  const high = Math.max(before, position);

  return (
    <figure className="needle" aria-hidden="false" style={{ margin: "24px 0 4px" }}>
      <figcaption className="sr-only">
        {DIMENSION_LABELS[key] ?? key}: {before} out of 100 now, {after} after this change.
      </figcaption>
      <span className="needle__cap" style={{ left: `${before}%` }}>
        {before}
      </span>
      <span className="needle__cap needle__cap--after" style={{ left: `${after}%`, top: "34px" }}>
        {after}
      </span>
      <span className="needle__track" />
      <span className="needle__span" style={{ left: `${low}%`, width: `${high - low}%` }} />
      <span className="needle__ghost" style={{ left: `${before}%` }} />
      <span className="needle__tick" style={{ left: `${position}%` }} />
    </figure>
  );
}

/**
 * Ce qui change, et tout ce qui reste.
 *
 * Le verbe vient du backend. Afficher « Add a jacket » en titre et
 * « Change · Jacket » deux lignes plus bas revient a se contredire a l'ecran.
 */
function Ledger({
  changed,
  kept,
  verb,
}: {
  changed: string | null;
  kept: string[];
  verb: string;
}) {
  return (
    <ul className="ledger">
      {changed ? (
        <li className="ledger__row ledger__row--changed">
          <span className="ledger__verb">{verb}</span>
          <span>{ELEMENT_LABELS[changed] ?? changed}</span>
        </li>
      ) : null}
      {kept.map((element) => (
        <li key={element} className="ledger__row ledger__row--kept">
          <span className="ledger__verb">Keep</span>
          <span>{ELEMENT_LABELS[element] ?? element}</span>
        </li>
      ))}
    </ul>
  );
}

/**
 * La dimension mise en avant est celle qui bouge le plus : l'aiguille montre
 * ce que le moteur a réellement fait progresser, pas une métrique choisie
 * d'avance.
 */
function leadDimension(recommendation: Recommendation): string {
  const { before, after } = recommendation.impact;
  let best = Object.keys(before)[0] ?? "professional_presence";
  let bestGain = -Infinity;

  for (const key of Object.keys(before)) {
    const gain = (after[key] ?? 0) - (before[key] ?? 0);
    if (gain > bestGain) {
      best = key;
      bestGain = gain;
    }
  }
  return best;
}
