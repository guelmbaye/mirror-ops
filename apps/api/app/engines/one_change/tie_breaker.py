"""Departage deterministe (Doc 04 §16 / §24).

Si l'ecart entre deux candidats est < TIE_DELTA, on prefere, dans l'ordre :
1. le moindre effort ;
2. le meilleur context fit ;
3. la generation VTO la plus simple ;
4. l'explication la plus simple (ordre de priorite produit fige).
"""

from __future__ import annotations

from app.engines.one_change.tables import ACTION_PRIORITY
from app.engines.one_change.types import ScoredCandidate
from app.models.enums import ChangeAction


def _priority_index(candidate: ScoredCandidate) -> int:
    try:
        return ACTION_PRIORITY.index(candidate.action)
    except ValueError:  # pragma: no cover - securite
        return len(ACTION_PRIORITY)


def sort_candidates(candidates: list[ScoredCandidate]) -> list[ScoredCandidate]:
    """Tri stable et deterministe : score decroissant puis criteres de departage."""
    return sorted(
        candidates,
        key=lambda c: (
            -c.score,
            -c.simplicity,
            -c.features.context_fit,
            -c.features.vto_feasibility,
            _priority_index(c),
        ),
    )


def break_tie(candidates: list[ScoredCandidate], tie_delta: float) -> list[ScoredCandidate]:
    """Reordonne uniquement le groupe de tete situe dans la fenetre d'egalite."""
    if not candidates:
        return []
    ordered = sort_candidates(candidates)
    # NO_CHANGE est arbitre par la politique de seuils (marge), jamais par
    # l'effort : sinon "ne rien faire" gagnerait tous les quasi-ex aequo.
    changes = [c for c in ordered if c.action is not ChangeAction.NO_CHANGE]
    no_change = [c for c in ordered if c.action is ChangeAction.NO_CHANGE]
    if not changes:
        return ordered
    best_score = changes[0].score
    tied = [c for c in changes if best_score - c.score < tie_delta]
    rest = [c for c in changes if best_score - c.score >= tie_delta]
    if len(tied) <= 1:
        return sort_candidates(changes + no_change)
    tied_sorted = sorted(
        tied,
        key=lambda c: (
            -c.simplicity,
            -c.features.context_fit,
            -c.features.vto_feasibility,
            _priority_index(c),
        ),
    )
    return tied_sorted + rest + no_change
