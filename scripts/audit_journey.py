#!/usr/bin/env python3
"""Audit de bout en bout : chaque etape, chaque champ, chaque invariant.

Ce script deroule le parcours comme le fait l'interface, ecran par ecran, et
verifie ce que l'API renvoie a chaque etape. Il ne remplace pas les tests
unitaires : il controle le systeme ASSEMBLE, dans la configuration reelle de la
machine — mode YouCam, base de donnees, catalogue compris.

    python scripts/audit_journey.py
    python scripts/audit_journey.py --base-url http://localhost:8000 --photo moi.jpg

Sortie : une ligne par verification.
    OK    l'invariant tient
    WARN  fonctionne, mais quelque chose limitera la qualite ou la demo
    FAIL  contrat rompu

Code de sortie 1 des le premier FAIL : utilisable avant une demonstration.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

try:
    import httpx
except ImportError:  # pragma: no cover
    sys.exit("pip install httpx")

RESULTS: list[tuple[str, str, str]] = []


def check(level: str, label: str, detail: str = "") -> None:
    RESULTS.append((level, label, detail))
    colour = {"OK": "\033[32m", "WARN": "\033[33m", "FAIL": "\033[31m"}.get(level, "")
    print(f"  {colour}{level:<4}\033[0m {label}" + (f"  — {detail}" if detail else ""))


def expect(condition: bool, label: str, detail: str = "") -> bool:
    check("OK" if condition else "FAIL", label, "" if condition else detail)
    return condition


def synthetic_photo(width: int = 900, height: int = 1200) -> bytes:
    from PIL import Image

    image = Image.new("RGB", (width, height), (168, 140, 128))
    pixels = image.load()
    for y in range(0, height, 3):
        for x in range(0, width, 3):
            shift = (x * y) % 41 - 20
            r, g, b = pixels[x, y]
            pixels[x, y] = (
                max(0, min(255, r + shift)),
                max(0, min(255, g + shift)),
                max(0, min(255, b + shift)),
            )
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=94)
    return buffer.getvalue()


def check_media(client: httpx.Client, base_url: str, url: str, label: str) -> None:
    """Verifie qu'un media est reellement servi.

    `PUBLIC_BASE_URL` fabrique ces URLs. Si elle ne correspond pas a l'endroit
    ou l'API repond vraiment — port different, reverse proxy, conteneur — les
    images sont introuvables pour TOUT LE MONDE, alors que l'API repond 201.
    C'est une panne silencieuse cote configuration, pas cote code.
    """
    host = url.split("/api/v1/")[0]
    if host.rstrip("/") != base_url.rstrip("/"):
        check("WARN", f"{label} : PUBLIC_BASE_URL ne correspond pas a l'API interrogee",
              f"{host} vs {base_url}")
        url = base_url.rstrip("/") + "/api/v1/" + url.split("/api/v1/", 1)[1]

    try:
        response = client.get(url)
    except httpx.HTTPError as exc:
        check("FAIL", f"{label} introuvable", str(exc))
        return
    expect(response.status_code == 200, f"{label} servie",
           f"HTTP {response.status_code}")


def section(title: str) -> None:
    print(f"\n\033[1m{title}\033[0m")


def audit(client: httpx.Client, api: str, photo: bytes, args_base: str) -> None:
    # ---------------------------------------------------------- configuration
    section("Configuration")
    health = client.get(f"{api}/health/dependencies").json()
    print(f"       {json.dumps(health)}")
    expect(health["database"] == "ok", "base de donnees joignable")
    expect(health["storage"] == "ok", "stockage accessible")

    if health["youcam_mode"] == "mock":
        check("WARN", "YouCam en mode mock", "les apercus porteront « simulated »")
    elif health["youcam"] != "configured":
        check("FAIL", "YouCam en mode live mais pas pret", health["youcam"])
    else:
        check("OK", "YouCam configure en mode live")

    if health.get("face_detection") == "unavailable":
        check(
            "FAIL",
            "face detection unusable",
            "Skin AI will never be called and framing cannot be measured. "
            "Most likely the PyPI stub named `cv2` is shadowing OpenCV: "
            "pip uninstall -y cv2 && pip install opencv-python-headless",
        )
    else:
        check("OK", "face detection available")

    if health.get("garments") == "placeholder":
        check(
            "WARN",
            "catalogue de substitution",
            "un try-on reel echouera : scripts/import_garments.py, ou « Try a piece of your own »",
        )
    else:
        check("OK", "catalogue exploitable")

    # ------------------------------------------------------------ ecran 1 : session
    section("Ecran 1 — Home  ·  POST /sessions")
    session = client.post(f"{api}/sessions").json()
    print(f"       ← {json.dumps(session)}")
    expect("id" in session, "identifiant de session renvoye")
    expect(session["state"] == "SESSION_CREATED", "etat initial correct", session.get("state", ""))
    expect(session["expires_at"].endswith("Z"), "expiration horodatee en UTC")
    session_id = session["id"]

    # ------------------------------------------------------------ ecran 2 : moment
    section("Ecran 2 — Moment  ·  POST /moments")
    payload = {
        "session_id": session_id,
        "occasion": "presentation",
        "goal": "professional",
        "time_available": "<5m",
    }
    print(f"       → {json.dumps(payload)}")
    moment = client.post(f"{api}/moments", json=payload)
    expect(moment.status_code == 201, "moment accepte", moment.text[:120])

    invalid = client.post(f"{api}/moments", json={**payload, "occasion": "brunch"})
    expect(invalid.status_code == 422, "occasion inconnue refusee proprement")

    # ------------------------------------------------------------ ecran 3-4 : analyse
    section("Ecran 3-4 — Your look / Analyzing  ·  POST /appearance/analyze")
    outfit = {
        "jacket": {"present": True},
        "top": {"present": True},
        "bottom": {"present": True},
        "shoes": {"present": True},
        "accessories": {"present": False},
    }
    print(f"       → outfit = {json.dumps(outfit)}")
    response = client.post(
        f"{api}/appearance/analyze",
        data={"session_id": session_id, "outfit": json.dumps(outfit)},
        files={"image": ("look.jpg", photo, "image/jpeg")},
    )
    if not expect(response.status_code == 201, "analyse acceptee", response.text[:200]):
        return
    analysis = response.json()
    print(f"       ← image_quality={json.dumps(analysis['image_quality'])}")
    print(f"       ← data_confidence={analysis['data_confidence']}  skin_source={analysis['skin_source']}")
    print(f"       ← element_suitability={json.dumps(analysis['element_suitability'])}")

    expect(set(analysis["appearance"]) >= {"professional_presence", "visual_coherence"},
           "six dimensions d'apparence presentes")
    expect(analysis["image_url"], "photo servie par une URL signee")
    expect(0.0 <= analysis["data_confidence"] <= 1.0, "confiance des donnees normalisee")

    if analysis["skin"]["redness"] is None:
        check("WARN", "aucun signal peau", f"source = {analysis['skin_source']}")
    else:
        check("OK", "signal peau exploite", analysis["skin_source"])
    if analysis.get("skin_simulated"):
        check("WARN", "signal peau simule", "ce n'est pas un resultat YouCam")

    check_media(client, args_base, analysis["image_url"], "photo d'entree")

    # ------------------------------------------------------------ ecran 5 : decision
    section("Ecran 5 — One change  ·  POST /one-change/evaluate")
    decision = client.post(f"{api}/one-change/evaluate", json={"session_id": session_id})
    if not expect(decision.status_code == 201, "decision rendue", decision.text[:300]):
        check("FAIL", "le moteur refuse de decider",
              "un moteur de decision qui ne decide pas n'a pas d'usage")
        return
    recommendation = decision.json()["recommendation"]

    fit = recommendation.get("fit")
    print(f"       ← fit    = {json.dumps(fit)}")
    print(f"       ← action = {recommendation['action']}  label = {recommendation['label']}")
    print(f"       ← score  = {recommendation['score']}  confidence = {recommendation['confidence']}")
    print(f"       ← keep   = {recommendation['keep']}")

    expect(fit is not None, "verdict d'adequation present")
    if fit:
        expect(fit["state"] in {"FIT", "ALMOST_THERE", "MISMATCH"}, "verdict dans le vocabulaire produit")
        expect(0 <= fit["score"] <= 100, "score d'adequation en pourcentage")
        expect(bool(fit["headline"] and fit["detail"]), "verdict formule pour un humain")
        if fit["weakest_element"]:
            expect(fit["weakest_element"] in fit["detail"],
                   "l'element mis en cause est nomme dans la phrase")

    expect(recommendation["action"], "une action, et une seule")
    expect(bool(recommendation["why"]), "la decision est justifiee")
    expect(isinstance(recommendation["keep"], list), "ce qui reste est enumere")

    # Coherence entre ce qui est declare, ce qui change et ce qui reste.
    declared = {k for k, v in outfit.items() if v["present"]}
    absent = {k for k, v in outfit.items() if not v["present"]}
    kept = set(recommendation["keep"])
    expect(not (kept & absent), "aucune piece absente n'est « gardee »",
           f"gardees a tort : {sorted(kept & absent)}")
    expect(kept <= declared, "tout ce qui est garde a bien ete declare")

    element = {
        "CHANGE_JACKET": "jacket", "CHANGE_TOP": "top", "CHANGE_BOTTOM": "bottom",
        "CHANGE_SHOES": "shoes", "CHANGE_ACCESSORY": "accessories",
        "REMOVE_ACCESSORY": "accessories",
        # Le travail couleur se materialise sur le haut : l'invariant vaut aussi.
        "CHANGE_COLOR": "top",
    }.get(recommendation["action"])
    if element:
        expect(element not in kept, "la piece qui change n'est pas aussi « gardee »")
        if recommendation["action"] == "CHANGE_COLOR":
            expect("top" in recommendation["label"].lower(),
                   "le libelle annonce ce que l'apercu montrera", recommendation["label"])
        elif recommendation["is_addition"]:
            expect(element in absent, "un ajout ne vise qu'une piece absente")
            expect(recommendation["label"].lower().startswith("add"),
                   "le libelle dit « add », pas « change »", recommendation["label"])
        else:
            expect(element in declared, "un remplacement vise une piece declaree")

    if recommendation["action"] == "NO_CHANGE":
        expect(fit and fit["state"] == "FIT", "NO_CHANGE et verdict FIT concordent")
        expect(not recommendation["requires_vto"], "NO_CHANGE ne demande aucun apercu")
    if recommendation["action"] == "REMOVE_ACCESSORY":
        expect(not recommendation["requires_vto"], "un retrait ne demande aucun apercu")

    # ------------------------------------------------------------ ecran 6 : preuve
    section("Ecran 6 — Before / After  ·  POST /vto/generate")
    if not recommendation["requires_vto"]:
        check("OK", "aucun apercu attendu pour cette decision", recommendation["action"])
    else:
        vto = client.post(f"{api}/vto/generate", json={"session_id": session_id})
        if vto.status_code == 201:
            body = vto.json()
            print(f"       ← garment={body['garment_id']}  provider={body['provider']}  "
                  f"simulated={body['simulated']}  latency={body['latency_ms']}ms")
            expect(body["before_image_url"] and body["result_image_url"], "avant et apres disponibles")
            check_media(client, args_base, body["result_image_url"], "image resultat")
            if body["simulated"]:
                check("WARN", "apercu compose localement", "ne pas presenter comme un rendu YouCam")
        else:
            error = vto.json().get("error", {})
            check("FAIL", f"apercu impossible ({vto.status_code})",
                  f"{error.get('code')} · {error.get('details', {}).get('provider_code', '')}")
            check("OK", "l'echappatoire existe",
                  "« Try a piece of your own » sur l'ecran de decision")

    # ------------------------------------------------------------ ecran 7 + reprise
    section("Ecran 7 — Ready  ·  GET /sessions/{id}")
    detail = client.get(f"{api}/sessions/{session_id}").json()
    expect(set(detail) == {"session", "moment", "analysis", "recommendation", "vto"},
           "l'ecran final se reconstruit en une requete")
    expect(detail["recommendation"]["id"] == recommendation["id"],
           "la decision relue est identique a la decision rendue")
    expect(detail["moment"]["occasion"] == "presentation", "le moment est conserve")

    # ---------------------------------------------------------- le catalogue
    section("Catalogue")
    garments = client.get(f"{api}/garments").json()["garments"]
    fake = [g["id"] for g in garments if g.get("placeholder")]
    real = [g["id"] for g in garments if not g.get("placeholder")]
    print(f"       {len(real)} reelle(s) · {len(fake)} substitution(s)")
    if fake:
        check("WARN", f"{len(fake)} vetement(s) encore en aplat",
              ", ".join(fake[:6]) + (" …" if len(fake) > 6 else ""))
    if real:
        check("OK", f"{len(real)} vetement(s) exploitables par un try-on reel",
              ", ".join(real[:6]))

    # ------------------------------------------------------ chemins de secours
    section("Chemins de secours")
    own = client.post(
        f"{api}/garments/upload",
        data={"session_id": session_id},
        files={"image": ("piece.jpg", synthetic_photo(700, 900), "image/jpeg")},
    )
    expect(own.status_code == 201, "on peut televerser sa propre piece", own.text[:150])

    empty = client.post(f"{api}/sessions").json()["id"]
    client.post(f"{api}/moments", json={**payload, "session_id": empty})
    client.post(
        f"{api}/appearance/analyze",
        data={
            "session_id": empty,
            "outfit": json.dumps({k: {"present": False} for k in outfit}),
        },
        files={"image": ("look.jpg", photo, "image/jpeg")},
    )
    refused = client.post(f"{api}/one-change/evaluate", json={"session_id": empty})
    if refused.status_code == 201:
        check("FAIL", "une tenue vide devrait etre refusee")
    else:
        message = refused.json()["error"]["message"]
        expect("wearing" in message, "le refus demande de declarer la tenue", message)
        expect("clearer view" not in message, "le refus n'accuse pas la photo a tort", message)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit de bout en bout MIRROR OPS")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--photo", type=Path, default=None)
    args = parser.parse_args()

    api = args.base_url.rstrip("/") + "/api/v1"
    photo = args.photo.expanduser().read_bytes() if args.photo else synthetic_photo()

    print(f"\nMIRROR OPS — audit de bout en bout  ({args.base_url})")
    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        try:
            audit(client, api, photo, args.base_url.rstrip("/"))
        except httpx.ConnectError:
            # Cas de loin le plus frequent : l'API n'est simplement pas lancee.
            # Un code d'erreur systeme ne dit pas quoi faire ; la commande, si.
            check("FAIL", "API injoignable", f"rien n'ecoute sur {args.base_url}")
            print("\n  Lancez l'API dans un autre terminal :")
            print("      .\\scripts\\mirror-ops.ps1 dev-api        (Windows)")
            print("      make dev-api                            (macOS / Linux)")
            print("  Puis relancez cet audit.")
        except httpx.HTTPError as exc:
            check("FAIL", "API injoignable", str(exc))

    failures = [r for r in RESULTS if r[0] == "FAIL"]
    warnings = [r for r in RESULTS if r[0] == "WARN"]
    print(f"\n{len(RESULTS)} verifications · {len(failures)} FAIL · {len(warnings)} WARN")

    if failures:
        print("\nA corriger :")
        for _, label, detail in failures:
            print(f"  · {label}" + (f" — {detail}" if detail else ""))
    if warnings:
        print("\nA savoir :")
        for _, label, detail in warnings:
            print(f"  · {label}" + (f" — {detail}" if detail else ""))

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
