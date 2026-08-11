"""Moteur ONE CHANGE : pipeline de decision complet (Doc 04 §21).

INPUT -> Validate -> Normalize -> Build Context -> Generate Candidates ->
Score -> Threshold -> Tie-breaker -> Select Winner -> Explain -> Return.

Proprietes garanties :
- exactement UNE action retournee ;
- deterministe (meme contexte -> meme decision) ;
- explicable (chaque recommandation porte ses facteurs dominants) ;
- NO_CHANGE possible ;
- aucun appel reseau, aucune base de donnees, aucun LLM.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.engines.one_change.candidates import FilteredCandidate, generate_candidates
from app.engines.one_change.confidence import compute_confidence
from app.engines.one_change.fit import assess_fit
from app.engines.one_change.explanation import is_addition, label_for, build_explanation, keep_list
from app.engines.one_change.scorer import score_all
from app.engines.one_change.thresholds import ThresholdPolicy, apply_thresholds
from app.engines.one_change.tie_breaker import break_tie
from app.engines.one_change.types import (
    DecisionContext,
    DecisionOutcome,
    ScoredCandidate,
)
from app.models.enums import ACTION_LABEL, ChangeAction

logger = logging.getLogger("mirror_ops.one_change")


class InsufficientDataError(Exception):
    """Le Data Quality Gate (Doc 04 §20) rejette l'entree : demander une meilleure photo."""


@dataclass(frozen=True, slots=True)
class EngineConfig:
    threshold: ThresholdPolicy = ThresholdPolicy()
    tie_delta: float = 5.0


class OneChangeEngine:
    """Cœur decisionnel de MIRROR OPS."""

    def __init__(self, config: EngineConfig | None = None) -> None:
        self.config = config or EngineConfig()

    # ------------------------------------------------------------------ API
    def evaluate(self, context: DecisionContext) -> DecisionOutcome:
        self._validate(context)

        actions, dropped = generate_candidates(context)
        self._log_dropped(dropped)

        scored = score_all(context, actions)
        ranked = break_tie(scored, self.config.tie_delta)

        winner, selection_reason = apply_thresholds(ranked, self.config.threshold)
        runner_up = self._runner_up(ranked, winner)

        confidence_value, confidence_level = compute_confidence(context, winner, runner_up)
        explanation = build_explanation(context, winner, selection_reason)

        before = {k: int(round(v * 100)) for k, v in context.appearance.dimensions.items()}
        after = {k: int(round(v * 100)) for k, v in winner.projected_dimensions.items()}

        logger.info(
            "one_change_decision",
            extra={
                "action": str(winner.action),
                "score": winner.score,
                "selection_reason": selection_reason,
                "confidence": str(confidence_level),
            },
        )

        return DecisionOutcome(
            action=winner.action,
            label=label_for(context, winner.action),
            score=winner.score,
            confidence_level=confidence_level,
            confidence_value=confidence_value,
            explanation=explanation,
            keep=keep_list(context, winner.action),
            impact_before=before,
            impact_after=after,
            winner=winner,
            runner_up=runner_up,
            candidates=ranked,
            # Un retrait ne se prouve pas avec un catalogue de vetements :
            # il n'y a rien a essayer, seulement quelque chose a enlever.
            requires_vto=winner.action
            not in (ChangeAction.NO_CHANGE, ChangeAction.REMOVE_ACCESSORY),
            is_addition=is_addition(context, winner.action),
            fit=assess_fit(context, winner.action),
        )

    # -------------------------------------------------------------- helpers
    def _validate(self, context: DecisionContext) -> None:
        """Data Quality Gate (Doc 04 §20).

        Chaque cause a son motif : l'appelant doit pouvoir dire a l'utilisateur
        ce qu'il faut corriger. Confondre « photo illisible » et « on ne sait
        pas ce que vous portez » envoie reprendre une photo qui allait tres bien.
        """
        if not context.appearance.present_elements:
            raise InsufficientDataError("no_outfit_declared")
        if context.appearance.image_quality < self.config.threshold.min_image_quality:
            raise InsufficientDataError("image_unusable")

        # Il n'y a PAS de troisieme portail.
        #
        # Un refus doit ouvrir sur un geste precis : declarer sa tenue, ou
        # reprendre la photo. Une confiance globale trop basse ne designe ni
        # l'un ni l'autre — elle envoyait l'utilisateur reprendre des photos
        # indefiniment sans que rien ne change. Une confiance faible se DIT
        # (`confidence: low`), elle ne bloque pas : un moteur de decision qui
        # refuse de decider ne sert a rien.

    @staticmethod
    def _runner_up(ranked: list[ScoredCandidate], winner: ScoredCandidate) -> ScoredCandidate | None:
        for candidate in ranked:
            if candidate.action is not winner.action:
                return candidate
        return None

    @staticmethod
    def _log_dropped(dropped: list[FilteredCandidate]) -> None:
        for item in dropped:
            logger.debug(
                "candidate_filtered",
                extra={"action": str(item.action), "reason": item.reason},
            )


#: Instance par defaut, reutilisable (le moteur est sans etat).
default_engine = OneChangeEngine()
