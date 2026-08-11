"""Normalisation des reponses provider -> modele interne (Doc 05 §7).

YouCam peut retourner des formes variees selon les endpoints actives sur le
compte. Le mapper est le SEUL endroit qui connait ces formes.
"""

from __future__ import annotations

from typing import Any

#: Cles YouCam/Perfect Corp possibles -> nom interne MIRROR OPS.
SKIN_KEY_ALIASES: dict[str, str] = {
    "texture": "texture",
    "hd_texture": "texture",
    "skin_texture": "texture",
    "redness": "redness",
    "hd_redness": "redness",
    "oiliness": "oiliness",
    "hd_oiliness": "oiliness",
    "radiance": "radiance",
    "hd_radiance": "radiance",
    "moisture": "moisture",
    "hd_moisture": "moisture",
}

#: Observations effectivement utilisees par MIRROR OPS (Doc 05 §7 :
#: "Ne stocker que les informations reellement utilisees").
KEPT_OBSERVATIONS: tuple[str, ...] = ("texture", "redness", "oiliness", "radiance")


def _to_unit(value: Any) -> float | None:
    """Convertit un score provider (0-100 ou 0-1) en 0..1."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, dict):
        for key in ("score", "value", "raw_score", "ui_score"):
            if key in value:
                return _to_unit(value[key])
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        if number < 0:
            return None
        if number <= 1.0:
            return round(number, 4)
        return round(min(number, 100.0) / 100.0, 4)
    if isinstance(value, str):
        try:
            return _to_unit(float(value))
        except ValueError:
            return None
    return None


#: Cote YouCam, un score ELEVE signifie une peau SAINE (« a higher score
#: indicates healthier skin »). Le moteur, lui, raisonne en severite : plus la
#: rougeur est marquee, plus la valeur est haute. On inverse donc ces
#: metriques — sans quoi une peau parfaite serait lue comme tres marquee.
INVERTED_METRICS = frozenset({"redness", "oiliness", "texture"})


def _walk(payload: Any, found: dict[str, float]) -> None:
    if isinstance(payload, dict):
        # Forme v2 : output = [{"type": "hd_redness", "ui_score": 77, ...}]
        kind = payload.get("type")
        if isinstance(kind, str):
            internal = SKIN_KEY_ALIASES.get(kind.lower())
            if internal and internal not in found:
                unit = _to_unit(payload)
                if unit is not None:
                    found[internal] = unit
        for raw_key, raw_value in payload.items():
            internal = SKIN_KEY_ALIASES.get(str(raw_key).lower())
            if internal and internal not in found:
                unit = _to_unit(raw_value)
                if unit is not None:
                    found[internal] = unit
            _walk(raw_value, found)
    elif isinstance(payload, list):
        for item in payload:
            _walk(item, found)


def normalize_skin_payload(payload: Any) -> dict[str, float]:
    """Extrait les observations utiles, quelle que soit la forme de la reponse."""
    found: dict[str, float] = {}
    _walk(payload, found)
    for metric in INVERTED_METRICS:
        if metric in found:
            found[metric] = round(1.0 - found[metric], 4)
    return {k: v for k, v in found.items() if k in KEPT_OBSERVATIONS}


def extract_task_id(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in ("task_id", "taskId", "id"):
        if key in payload and isinstance(payload[key], (str, int)):
            return str(payload[key])
    result = payload.get("result") or payload.get("data")
    if isinstance(result, dict):
        return extract_task_id(result)
    return None


def extract_status(payload: Any) -> str:
    if not isinstance(payload, dict):
        return "unknown"
    for key in ("status", "state", "task_status"):
        value = payload.get(key)
        if isinstance(value, str):
            return value.lower()
    result = payload.get("result") or payload.get("data")
    if isinstance(result, dict):
        return extract_status(result)
    return "unknown"


#: Codes d'erreur de tache qui designent un probleme de PHOTO, pas de service.
#: Les remonter comme une panne serait trompeur : l'utilisateur peut agir.
IMAGE_TASK_ERRORS = frozenset({
    "error_no_face",
    "error_pose",
    "error_face_parsing",
    "error_multiple_people",
    "error_no_shoulder",
    "error_large_face_angle",
    "error_unsupport_ratio",
    "error_src_face_too_small",
    "error_src_face_out_of_bound",
    "error_below_min_image_size",
    "error_exceed_max_image_size",
    "error_lighting_dark",
    "error_decode_image",
    "error_download_image",
    "exceed_max_filesize",
    "error_nsfw_content_detected",
})


def extract_task_error(payload: Any) -> tuple[str | None, str | None]:
    """Code et message d'erreur d'une tache terminee en echec.

    Sans cela, un echec de tache remonte comme « Provider task failed (error) »
    et ne dit rien de ce qu'il faut corriger — alors que l'API nomme la cause.
    """
    code: str | None = None
    message: str | None = None

    def walk(node: Any) -> None:
        nonlocal code, message
        if isinstance(node, dict):
            for key, value in node.items():
                lowered = str(key).lower()
                if isinstance(value, str):
                    if lowered in ("error_code", "errorcode") and code is None:
                        code = value
                    elif lowered in ("error", "error_message", "message") and message is None:
                        message = value
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)

    # Le provider renvoie parfois le code dans le champ `error` plutot que dans
    # `error_code` : « error_editing_failed » est un code, pas une phrase.
    if code is None and message and _looks_like_a_code(message):
        code, message = message, None
    return code, message


def _looks_like_a_code(value: str) -> bool:
    token = value.strip()
    if " " in token or not token:
        return False
    return token.islower() and ("_" in token) and token.replace("_", "").isalnum()


def extract_result_urls(payload: Any) -> list[str]:
    """Recupere les URLs de resultat (image ou archive) d'une reponse de tache."""
    urls: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(value, str) and value.startswith("http") and (
                    "url" in str(key).lower() or "download" in str(key).lower()
                ):
                    urls.append(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return urls
