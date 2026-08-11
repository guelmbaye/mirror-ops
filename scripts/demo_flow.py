#!/usr/bin/env python3
"""Deroule le parcours MIRROR OPS complet contre une API en cours d'execution.

Usage :
    python scripts/demo_flow.py [--base-url http://localhost:8000] [--photo chemin.jpg]

Sert a :
- valider une installation ("Definition of Done", Doc 09 §27) ;
- repeter la demo (Doc 12 §13 : "Run at least 5 complete tests") ;
- mesurer les latences reelles avant enregistrement video.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:  # pragma: no cover
    sys.exit("pip install httpx")


def synthetic_photo() -> bytes:
    from PIL import Image

    image = Image.new("RGB", (720, 1280), (168, 140, 128))
    pixels = image.load()
    for y in range(0, 1280, 4):
        for x in range(0, 720, 4):
            shift = (x * y) % 41 - 20
            r, g, b = pixels[x, y]
            pixels[x, y] = (
                max(0, min(255, r + shift)),
                max(0, min(255, g + shift)),
                max(0, min(255, b + shift)),
            )
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()


def step(label: str, started: float) -> None:
    print(f"  ✓ {label:<28} {int((time.perf_counter() - started) * 1000):>5} ms")


def main() -> int:
    parser = argparse.ArgumentParser(description="MIRROR OPS demo flow")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--photo", type=Path, default=None)
    parser.add_argument("--occasion", default="presentation")
    parser.add_argument("--goal", default="professional")
    parser.add_argument("--time", dest="time_available", default="<5m")
    parser.add_argument("--outfit", type=Path, default=None, help="JSON decrivant la tenue")
    args = parser.parse_args()

    photo = args.photo.read_bytes() if args.photo else synthetic_photo()
    outfit = args.outfit.read_text() if args.outfit else None
    api = args.base_url.rstrip("/") + "/api/v1"
    journey_started = time.perf_counter()

    with httpx.Client(timeout=120.0) as client:
        print(f"\nMIRROR OPS — demo flow ({args.base_url})\n")

        t = time.perf_counter()
        session = client.post(f"{api}/sessions").raise_for_status().json()
        step("session", t)

        t = time.perf_counter()
        client.post(
            f"{api}/moments",
            json={
                "session_id": session["id"],
                "occasion": args.occasion,
                "goal": args.goal,
                "time_available": args.time_available,
            },
        ).raise_for_status()
        step("moment", t)

        t = time.perf_counter()
        data = {"session_id": session["id"]}
        if outfit:
            data["outfit"] = outfit
        analysis = client.post(
            f"{api}/appearance/analyze",
            data=data,
            files={"image": ("look.jpg", photo, "image/jpeg")},
        ).raise_for_status().json()
        step("appearance + skin AI", t)

        t = time.perf_counter()
        recommendation = client.post(
            f"{api}/one-change/evaluate", json={"session_id": session["id"]}
        ).raise_for_status().json()["recommendation"]
        step("ONE CHANGE", t)

        print("\n  ┌─────────────────────────────────────────────")
        print(f"  │ ONE CHANGE   {recommendation['label']}")
        print(f"  │ Impact       {recommendation['score']}/100")
        print(f"  │ Confidence   {recommendation['confidence']}")
        print(f"  │ Keep         {', '.join(recommendation['keep']) or '—'}")
        print(f"  │ Why          {recommendation['why']}")
        print("  └─────────────────────────────────────────────\n")

        if recommendation["requires_vto"]:
            t = time.perf_counter()
            vto = client.post(
                f"{api}/vto/generate", json={"session_id": session["id"]}
            ).raise_for_status().json()
            step("apparel VTO", t)
            print(f"\n  BEFORE  {vto['before_image_url']}")
            print(f"  AFTER   {vto['result_image_url']}")
            if vto["simulated"]:
                print("  ⚠ apercu compose localement (YOUCAM_MODE=mock) — pas un rendu YouCam")
        else:
            print("  NO_CHANGE → aucun appel VTO (unites preservees)")

        detail = client.get(f"{api}/sessions/{session['id']}").raise_for_status().json()
        total_ms = int((time.perf_counter() - journey_started) * 1000)
        print(f"\n  Etat final : {detail['session']['state']}")
        print(f"  Parcours complet : {total_ms} ms")
        print(f"  Skin observations : {json.dumps(analysis['skin'])}\n")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
