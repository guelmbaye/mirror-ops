"""Recadrage du visage pour Skin AI, depuis la photo de tenue.

Le probleme : Skin AI exige que le visage occupe **au moins 60 % de la largeur**
de l'image, sinon `error_src_face_too_small`. MIRROR OPS, lui, demande une photo
de la TENUE, ou le visage est forcement petit.

Deux exigences incompatibles sur une meme photo — mais le parcours doit rester a
une seule prise de vue : ajouter un second cliche ajouterait un ecran, et la
contrainte est le produit.

La reponse est donc ici : on detecte le visage cote serveur et on en extrait un
cadrage conforme. La photo d'origine, elle, reste intacte pour le VTO et pour
l'affichage — on ne recadre que ce qui part vers l'analyse de peau.

OpenCV est optionnel. S'il manque, ce module le dit et le parcours continue sans
signal peau, plutot que d'echouer : Skin AI *informe* la decision, il ne la prend
pas.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass

from PIL import Image

logger = logging.getLogger("mirror_ops.face_crop")

#: Part du cadrage occupee par le visage, dans les DEUX dimensions.
#:
#: Calibre contre l'API reelle (`scripts/probe_skin.py`), pas d'apres la
#: documentation. Sur un plan en pied — visage de 289 px — les ratios 0.68,
#: 0.80 et 0.92 passent tous les trois. Le choix se joue donc ailleurs : plus
#: le cadrage est serre, plus il faut l'agrandir pour atteindre le cote court
#: minimal, et plus les pixels sont interpoles. Or `texture` est l'une des
#: metriques mesurees : l'agrandissement degrade precisement ce qu'on observe.
#:
#: 0.72 garde les deux axes au-dessus de 60 % tout en ramenant l'agrandissement
#: de 1.33x a 1.20x sur cette photo.
#:
#: A retenir : les valeurs renvoyees varient avec le cadrage (radiance 0.63 a
#: 0.71 selon le ratio). Ce sont des observations relatives, pas des mesures
#: absolues — le produit les presente comme telles.
TARGET_FACE_RATIO = 0.72

#: Reglage de repli, tente une seule fois si le provider juge le visage trop
#: petit malgre tout. Une unite de plus, seulement quand la premiere a echoue.
FALLBACK_FACE_RATIO = 0.92

#: Le cadrage reste legerement portrait pour garder front et menton, mais assez
#: proche du carre pour que le visage domine aussi la hauteur.
CROP_ASPECT = 1.12

#: Cote court minimal exige par l'analyse SD.
MIN_SHORT_SIDE = 480

#: En deca, le visage est trop petit dans l'original : agrandir ne creerait que
#: du flou, et l'analyse porterait sur des pixels inventes par l'interpolation.
MIN_DETECTED_FACE_WIDTH = 140


@dataclass(frozen=True, slots=True)
class FaceCrop:
    image_bytes: bytes
    mime_type: str
    width: int
    height: int
    face_ratio: float
    #: La boite detectee, reutilisee pour estimer le cadrage sans redetecter.
    face_box: tuple[int, int, int, int] | None = None


#: Ce qui manque, quand quelque chose manque. Renseigne au premier appel.
_UNAVAILABLE_REASON: str | None = None


def opencv_status() -> tuple[bool, str]:
    """La detection de visage est-elle REELLEMENT utilisable ?

    Verifier l'import ne suffit pas. Deux facons d'avoir un `cv2` importable et
    inutilisable, toutes deux observees :

    - **OpenCV 5.0** a supprime les cascades de Haar. `CascadeClassifier`
      n'existe plus, et `cv2.data.haarcascades` pointe vers un repertoire vide.
      Un `pip install opencv-python-headless` sans borne haute installe 5.x.
    - Le paquet PyPI nomme `cv2` est sans rapport et fournit un module du meme
      nom, qui masque le vrai.

    Dans les deux cas le module s'importe proprement et echoue a chaque appel.
    Skin AI n'est alors jamais appele et le cadrage retombe sur « inconnu ».
    """
    try:
        import cv2
    except ImportError:
        return False, "opencv is not installed"

    version = getattr(cv2, "__version__", "unknown")

    if not hasattr(cv2, "CascadeClassifier"):
        if version.startswith("5."):
            return False, (
                f"OpenCV {version} removed Haar cascades. "
                'Run: pip install "opencv-python-headless>=4.10,<5"'
            )
        installed = getattr(cv2, "__file__", "unknown location")
        return False, (
            f"the installed `cv2` ({installed}) has no CascadeClassifier and is "
            'not usable OpenCV. Run: pip uninstall -y cv2 && '
            'pip install "opencv-python-headless>=4.10,<5"'
        )

    if not hasattr(cv2, "data"):
        return False, f"OpenCV {version} is installed without its data module"

    try:
        classifier = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_alt2.xml"
        )
    except Exception as exc:  # pragma: no cover - installation cassee
        return False, f"opencv is present but unusable: {exc}"

    if classifier.empty():
        return False, (
            f"OpenCV {version} ships no Haar cascade files "
            f"({cv2.data.haarcascades} is empty). "
            'Run: pip install "opencv-python-headless>=4.10,<5"'
        )
    return True, "ok"


def opencv_available() -> bool:
    """Verifiable au demarrage, plutot que decouvert au premier parcours."""
    return opencv_status()[0]


#: Plusieurs classifieurs, essayes dans l'ordre.
#:
#: `default` echoue sur un visage portant des lunettes de soleil — il s'appuie
#: fortement sur la region des yeux — et retourne alors une fausse detection
#: ailleurs dans l'image. Sur une photo reelle, il a designe un morceau de veste
#: a mi-hauteur : le produit envoyait donc du tissu a Skin AI et deduisait un
#: cadrage faux. `alt2` trouve le vrai visage sur la meme image.
CASCADES = (
    "haarcascade_frontalface_alt2.xml",
    "haarcascade_frontalface_default.xml",
    "haarcascade_frontalface_alt.xml",
    "haarcascade_profileface.xml",
)

#: Un visage se trouve dans la partie haute d'un portrait. Au-dela, c'est du
#: torse ou de l'arriere-plan.
MAX_FACE_TOP_RATIO = 0.55


def _plausible(box, size) -> bool:
    """Ecarte les fausses detections evidentes.

    Une boite carree quelque part dans une veste satisfait un classifieur de
    Haar ; elle ne satisfait pas la geometrie d'un portrait.
    """
    x, y, w, h = box
    width, height = size
    if w <= 0 or h <= 0:
        return False
    # Assez haut dans l'image.
    if (y + h / 2) / height > MAX_FACE_TOP_RATIO:
        return False
    # Ni minuscule, ni couvrant toute l'image.
    if not (0.04 <= w / width <= 0.95):
        return False
    return True


#: Une analyse detecte le visage deux fois — une fois pour le recadrage Skin AI,
#: une fois pour estimer le cadrage. La detection est deterministe et couteuse
#: (plusieurs classifieurs sur une image pleine resolution) : on memorise le
#: dernier resultat plutot que de faire circuler l'etat a travers trois
#: fonctions. Une seule entree suffit : les deux appels sont consecutifs.
_LAST_DETECTION: tuple[str, tuple[int, int, int, int] | None] | None = None


def detect_largest_face(image_bytes: bytes) -> tuple[int, int, int, int] | None:
    """Retourne (x, y, w, h) du plus grand visage plausible, ou None."""
    global _LAST_DETECTION

    from hashlib import blake2b

    digest = blake2b(image_bytes, digest_size=16).hexdigest()
    if _LAST_DETECTION is not None and _LAST_DETECTION[0] == digest:
        return _LAST_DETECTION[1]

    found = _detect(image_bytes)
    _LAST_DETECTION = (digest, found)
    return found


def _detect(image_bytes: bytes) -> tuple[int, int, int, int] | None:
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None

    global _UNAVAILABLE_REASON
    ready, reason = opencv_status()
    if not ready:
        if _UNAVAILABLE_REASON != reason:
            # Une fois, pas a chaque requete : la cause ne change pas.
            _UNAVAILABLE_REASON = reason
            logger.error("face_detection_unavailable", extra={"reason": reason})
        return None

    try:
        buffer = np.frombuffer(image_bytes, dtype=np.uint8)
        frame = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        if frame is None:
            return None
        gray = cv2.equalizeHist(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
        height, width = gray.shape
        minimum = max(60, int(min(width, height) * 0.06))

        candidates: list[tuple[int, int, int, int]] = []
        for name in CASCADES:
            cascade = cv2.CascadeClassifier(cv2.data.haarcascades + name)
            if cascade.empty():  # pragma: no cover - installation incomplete
                continue
            found = cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(minimum, minimum)
            )
            plausible = [
                (int(x), int(y), int(w), int(h))
                for x, y, w, h in found
                if _plausible((x, y, w, h), (width, height))
            ]
            if plausible:
                candidates.extend(plausible)
                # Le premier classifieur qui donne un resultat credible suffit :
                # ils sont ordonnes par fiabilite observee.
                break

        if not candidates:
            logger.info("face_not_found")
            return None
        return max(candidates, key=lambda box: box[2] * box[3])
    except Exception as exc:  # pragma: no cover - robustesse
        logger.warning("face_detection_failed", extra={"reason": str(exc)})
        return None


def compute_crop_box(
    face: tuple[int, int, int, int],
    size: tuple[int, int],
    target: float = TARGET_FACE_RATIO,
) -> tuple[int, int, int, int]:
    """Cadre centre sur le visage, dimensionne pour atteindre le ratio cible.

    Le cadre est ramene dans les bornes de l'image par translation plutot que par
    rognage : rogner reduirait la largeur et ferait remonter le ratio au-dela du
    cadrage voulu, ce qui coupe le front ou le menton.
    """
    fx, fy, fw, fh = face
    image_w, image_h = size

    crop_w = min(image_w, max(1, round(fw / target)))
    crop_h = min(image_h, max(1, round(crop_w * CROP_ASPECT)))

    center_x = fx + fw / 2
    # Le visage est place un peu au-dessus du centre : on garde le front, qui
    # porte une partie des metriques (rides, pores).
    center_y = fy + fh * 0.45

    left = round(center_x - crop_w / 2)
    top = round(center_y - crop_h / 2)
    left = max(0, min(left, image_w - crop_w))
    top = max(0, min(top, image_h - crop_h))
    return left, top, left + crop_w, top + crop_h


def crop_face_for_skin(
    image_bytes: bytes, target: float = TARGET_FACE_RATIO
) -> FaceCrop | None:
    """Extrait un cadrage conforme a Skin AI, ou None si ce n'est pas possible."""
    face = detect_largest_face(image_bytes)
    if face is None:
        return None
    if face[2] < MIN_DETECTED_FACE_WIDTH:
        logger.info("face_too_small_to_crop", extra={"face_width": face[2]})
        return None

    with Image.open(io.BytesIO(image_bytes)) as source:
        image = source.convert("RGB")
        box = compute_crop_box(face, image.size, target)
        crop = image.crop(box)

        short_side = min(crop.size)
        upscale = 1.0
        if short_side < MIN_SHORT_SIDE:
            upscale = MIN_SHORT_SIDE / short_side
            crop = crop.resize(
                (round(crop.width * upscale), round(crop.height * upscale)), Image.LANCZOS
            )
            # Sur une photo en pied, le visage fait souvent 300 px : le
            # recadrage part alors sous le minimum et doit etre agrandi. Les
            # pixels ajoutes sont interpoles — l'analyse porte sur une image
            # adoucie, et le provider peut la refuser. Ce n'est pas une erreur,
            # mais cela doit se voir dans les logs.
            logger.info(
                "skin_crop_upscaled",
                extra={"factor": round(upscale, 2), "from": short_side, "to": MIN_SHORT_SIDE},
            )

        output = io.BytesIO()
        crop.save(output, format="JPEG", quality=92)

    face_ratio = round(face[2] / (box[2] - box[0]), 3)
    return FaceCrop(
        image_bytes=output.getvalue(),
        mime_type="image/jpeg",
        width=crop.width,
        height=crop.height,
        face_ratio=face_ratio,
        face_box=face,
    )
