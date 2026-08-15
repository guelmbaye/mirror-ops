#!/usr/bin/env python3
"""Teste le recadrage visage contre la vraie API Skin AI, ratio par ratio.

YouCam exige que le visage occupe plus de 60 % de la largeur. Nous recadrons
donc le visage depuis la photo de tenue — mais un premier reglage satisfaisant
cette regle a quand meme recu `error_src_face_too_small`. Impossible de savoir
de l'exterieur si leur mesure porte sur une autre dimension, ou si leur
detecteur trouve un visage plus petit que le notre.

Ce script tranche empiriquement : il envoie le MEME visage a plusieurs niveaux
de serrage et rapporte lequel passe.

    python scripts/probe_skin.py ma-photo.jpg
    python scripts/probe_skin.py ma-photo.jpg --ratios 0.7,0.8,0.9

Chaque ratio teste consomme une unite d'analyse.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "apps" / "api", ROOT):
    if (candidate / "app").is_dir():
        sys.path.insert(0, str(candidate))
        break

from app.core.config import get_settings  # noqa: E402
from app.integrations.youcam.exceptions import YouCamError  # noqa: E402
from app.integrations.youcam.skin_ai import SkinAIService  # noqa: E402
from app.services.face_crop import (  # noqa: E402
    compute_crop_box,
    crop_face_for_skin,
    detect_largest_face,
    opencv_status,
)


async def main() -> int:
    parser = argparse.ArgumentParser(description="Probe Skin AI crop ratios")
    parser.add_argument("photo", type=Path)
    parser.add_argument("--ratios", default="0.68,0.80,0.92",
                        help="comma-separated face-to-crop ratios to try")
    args = parser.parse_args()

    photo = args.photo.expanduser()
    if not photo.exists():
        print(f"Photo introuvable : {photo.resolve()}")
        return 2

    settings = get_settings()
    print(f"mode : {settings.YOUCAM_MODE}")

    ready, reason = opencv_status()
    if not ready:
        print(f"Detection de visage indisponible : {reason}")
        return 2

    data = photo.read_bytes()
    face = detect_largest_face(data)
    if face is None:
        print("Aucun visage detecte dans cette photo — Skin AI ne peut rien en faire.")
        return 1

    from PIL import Image
    import io

    with Image.open(io.BytesIO(data)) as image:
        size = image.size
    print(f"photo  : {size[0]}x{size[1]}")
    print(f"visage : {face[2]}x{face[3]} px, soit {face[3] / size[1]:.1%} de la hauteur")

    from app.services.face_crop import MIN_SHORT_SIDE
    from app.services.framing import HUMAN_LABEL, estimate_framing

    estimate = estimate_framing(data, face=face)
    print(f"cadrage : {estimate.framing} ({HUMAN_LABEL[estimate.framing]})")
    print(f"visible : {', '.join(sorted(str(e) for e in estimate.visible))}")

    preview = compute_crop_box(face, size)
    short = min(preview[2] - preview[0], preview[3] - preview[1])
    if short < MIN_SHORT_SIDE:
        print(f"\n  ! le recadrage part a {short} px de cote court et sera agrandi "
              f"{MIN_SHORT_SIDE / short:.2f}x — les pixels ajoutes sont interpoles,")
        print("    et le provider peut refuser une image adoucie.")

    if not settings.is_live_youcam:
        print("\nYOUCAM_MODE n'est pas `live` : geometrie verifiee, aucun appel envoye.")
        print("Passez en live pour savoir quel ratio le provider accepte.")
        return 0

    print()
    service = SkinAIService()
    results: list[tuple[float, str]] = []
    try:
        for ratio in [float(r) for r in args.ratios.split(",")]:
            box = compute_crop_box(face, size, ratio)
            width, height = box[2] - box[0], box[3] - box[1]
            crop = crop_face_for_skin(data, target=ratio)
            if crop is None:
                results.append((ratio, "crop impossible"))
                continue

            label = (f"ratio {ratio:.2f} · {width}x{height} · "
                     f"largeur {face[2] / width:.0%} hauteur {face[3] / height:.0%}")
            try:
                result = await service.analyze(crop.image_bytes, crop.mime_type)
            except YouCamError as exc:
                # Tout ce que le provider a dit, sans filtre : un code vide ne
                # doit pas laisser l'utilisateur sans piste.
                code = getattr(exc, "provider_code", None) or ""
                detail = (getattr(exc, "detail", None) or "").strip()
                print(f"  x {label}")
                print(f"      classe   : {type(exc).__name__}")
                print(f"      message  : {exc}")
                if code:
                    print(f"      code     : {code}")
                if detail:
                    print(f"      detail   : {detail[:300]}")
                sent = len(crop.image_bytes)
                from PIL import Image as _Image

                with _Image.open(io.BytesIO(crop.image_bytes)) as _sent:
                    print(f"      envoye   : {_sent.width}x{_sent.height}, {sent // 1024} Ko")
                results.append((ratio, code or type(exc).__name__))
                continue

            observed = ", ".join(f"{k}={v}" for k, v in sorted(result.observations.items()))
            print(f"  + {label}  ->  OK  ({observed or 'aucune metrique'})")
            results.append((ratio, "ok"))
    finally:
        from app.integrations.youcam.client import close_youcam_client

        await close_youcam_client()

    passing = [ratio for ratio, outcome in results if outcome == "ok"]
    print()
    if passing:
        print(f"Ratio le plus permissif qui passe : {min(passing):.2f}")
        print("Reglez TARGET_FACE_RATIO dans app/services/face_crop.py sur cette valeur")
        print("ou juste au-dessus.")
        return 0

    # Ne pas accuser la photo quand l'echec est ailleurs. La premiere version
    # concluait « essayez sans lunettes » alors que la cle API n'etait pas lue.
    outcomes = {outcome for _, outcome in results}
    if outcomes <= {"YouCamAuthError"}:
        print("Aucun appel n'a atteint YouCam : la configuration est en cause,")
        print("pas la photo. Verifiez apps/api/.env :")
        print("    YOUCAM_MODE=live")
        print("    YOUCAM_AUTH_MODE=api_key")
        print("    YOUCAM_API_KEY=...")
        print("puis  curl localhost:8000/api/v1/health/dependencies")
        return 2

    if "error_src_face_too_small" in outcomes:
        print("Le visage reste juge trop petit a tous les serrages.")
        print(f"Il fait {face[2]} px dans une photo de {size[0]}x{size[1]} : un plan en")
        print("pied ne peut pas donner davantage sans inventer des pixels. Skin AI")
        print("restera absent sur ce cadrage — le parcours fonctionne sans lui.")
        return 1

    if "empty_result" in outcomes:
        print("La tache a abouti mais nous n'avons rien su lire de sa reponse.")
        print("Le detail imprime ci-dessus contient la charge utile brute : c'est")
        print("notre lecture qu'il faut corriger, pas la photo.")
        return 1

    print("Aucun ratio n'est passe. Deux hypotheses restent :")
    print("  · le detecteur de YouCam ne trouve pas ce visage (lunettes de soleil,")
    print("    angle, contre-jour) — aucun recadrage n'y changera rien ;")
    print("  · la photo est trop peu definie une fois recadree.")
    print("Essayez une photo de face, sans lunettes, en lumiere frontale.")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
