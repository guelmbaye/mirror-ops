"""Essayer sa propre piece.

Le catalogue existe pour que le parcours ne s'arrete jamais. Mais quelqu'un qui
hesite devant une piece precise a une bien meilleure raison de vouloir la voir
sur lui — et cela supprime au passage toute dependance a la qualite du
catalogue livre.
"""

from __future__ import annotations

import io

from PIL import Image

from app.integrations.youcam import set_providers
from app.integrations.youcam.mock import LocalCompositeVTOService
from app.integrations.youcam.models import GarmentRef
from tests.conftest import make_image


def garment_photo(width: int = 700, height: int = 900) -> bytes:
    """Une « photo » de vetement : bruitee, donc pas un aplat."""
    return make_image(width=width, height=height, noisy=True)


class CapturingVTOProvider(LocalCompositeVTOService):
    provider_name = "local_composite"

    def __init__(self) -> None:
        self.seen: GarmentRef | None = None

    async def generate(self, source_image, garment: GarmentRef, *, source_mime="image/jpeg"):
        self.seen = garment
        return await super().generate(source_image, garment, source_mime=source_mime)


async def test_a_user_can_try_their_own_piece(client, flow):
    provider = CapturingVTOProvider()
    set_providers(vto=provider)

    session_id = await flow.session()
    await flow.moment(session_id)
    await flow.analyze(session_id)
    recommendation = await flow.one_change(session_id)
    assert recommendation["requires_vto"]

    upload = await client.post(
        "/api/v1/garments/upload",
        data={"session_id": session_id},
        files={"image": ("ma-veste.jpg", garment_photo(), "image/jpeg")},
    )
    assert upload.status_code == 201
    asset_id = upload.json()["id"]

    response = await client.post(
        "/api/v1/vto/generate",
        json={"session_id": session_id, "garment_asset_id": asset_id},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["garment_id"] == asset_id
    # C'est bien la piece de l'utilisateur qui part au provider.
    assert provider.seen is not None
    assert provider.seen.garment_id == asset_id
    assert provider.seen.name == "Your own piece"


async def test_the_uploaded_piece_is_normalised_before_use(client, flow):
    """Meme traitement que le catalogue : format, taille et fond alignes."""
    session_id = await flow.session()
    await flow.moment(session_id)

    small = make_image(width=400, height=520, noisy=True)
    upload = await client.post(
        "/api/v1/garments/upload",
        data={"session_id": session_id},
        files={"image": ("petite.png", small, "image/png")},
    )
    assert upload.status_code == 201
    body = upload.json()
    assert max(body["width"], body["height"]) >= 1024


async def test_an_unreadable_file_is_refused_clearly(client, flow):
    session_id = await flow.session()
    await flow.moment(session_id)

    response = await client.post(
        "/api/v1/garments/upload",
        data={"session_id": session_id},
        files={"image": ("pas-une-image.jpg", b"not-an-image", "image/jpeg")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_IMAGE"


async def test_a_piece_from_another_session_is_not_reachable(client, flow):
    """Les medias d'une session restent dans cette session."""
    first = await flow.session()
    await flow.moment(first)
    upload = await client.post(
        "/api/v1/garments/upload",
        data={"session_id": first},
        files={"image": ("veste.jpg", garment_photo(), "image/jpeg")},
    )
    asset_id = upload.json()["id"]

    second = await flow.session()
    await flow.moment(second)
    await flow.analyze(second)
    await flow.one_change(second)

    response = await client.post(
        "/api/v1/vto/generate",
        json={"session_id": second, "garment_asset_id": asset_id},
    )
    # Retombe sur le catalogue : l'identifiant n'existe pas pour cette session.
    assert response.status_code == 404


async def test_the_catalog_still_works_untouched(client, flow):
    """Ouvrir l'import ne retire rien : le parcours par defaut ne change pas."""
    session_id = await flow.session()
    await flow.moment(session_id)
    await flow.analyze(session_id)
    await flow.one_change(session_id)

    response = await flow.vto(session_id)
    assert response.status_code == 201
    assert response.json()["garment_id"].startswith(("jacket", "top", "bottom", "shoes", "accessory"))


async def test_a_failure_says_which_garment_was_used(client, flow):
    """Quatre echanges ont ete perdus faute de savoir si le catalogue ou la
    piece de l'utilisateur etait en cause. L'echec doit le dire lui-meme."""
    from app.integrations.youcam.exceptions import YouCamProviderError

    class FailingVTO:
        provider_name = "youcam_apparel_vto"

        async def generate(self, source_image, garment, *, source_mime="image/jpeg"):
            raise YouCamProviderError(
                "Provider task failed (error)",
                detail="error_editing_failed",
                provider_code="error_editing_failed",
            )

    set_providers(vto=FailingVTO())

    session_id = await flow.session()
    await flow.moment(session_id)
    await flow.analyze(session_id)
    await flow.one_change(session_id)

    # Echec sur le catalogue.
    catalog_failure = (await flow.vto(session_id)).json()["error"]["details"]
    assert catalog_failure["garment_source"] == "catalog"
    assert catalog_failure["garment_id"].startswith(("jacket", "top", "bottom", "shoes", "accessory"))
    # `garment_bytes` et le code provider restent reserves au developpement.
    assert "garment_bytes" not in catalog_failure or catalog_failure["garment_bytes"] > 0

    # Echec sur une piece televersee.
    upload = await client.post(
        "/api/v1/garments/upload",
        data={"session_id": session_id},
        files={"image": ("ma-veste.jpg", garment_photo(), "image/jpeg")},
    )
    asset_id = upload.json()["id"]
    own_failure = (
        await client.post(
            "/api/v1/vto/generate",
            json={"session_id": session_id, "garment_asset_id": asset_id},
        )
    ).json()["error"]["details"]

    assert own_failure["garment_source"] == "uploaded"
    assert own_failure["garment_id"] == asset_id
    # Les deux cas se distinguent sans ambiguite.
    assert own_failure["garment_source"] != catalog_failure["garment_source"]


def test_an_extreme_aspect_ratio_is_letterboxed_not_cropped():
    """Une photo en bande cassait l'essayage.

    1306x4080, soit 1:3.12 — deux fois plus etiree qu'un portrait de telephone.
    Le modele attend une personne dans un cadre de photo, pas dans une colonne.
    Recadrer serait pire : sur un plan en pied, retirer de la hauteur coupe les
    chaussures, c'est-a-dire une piece que le produit peut recommander.
    """
    import io

    from PIL import Image

    from app.services.vto_service import (
        MAX_SOURCE_ASPECT,
        MAX_SOURCE_LONG_SIDE,
        _bounded,
    )

    buffer = io.BytesIO()
    Image.new("RGB", (1306, 4080), (150, 130, 120)).save(buffer, format="JPEG")

    with Image.open(io.BytesIO(_bounded(buffer.getvalue()))) as result:
        width, height = result.size

    assert height / width <= MAX_SOURCE_ASPECT
    assert max(width, height) <= MAX_SOURCE_LONG_SIDE
    # La hauteur relative est preservee : rien n'a ete coupe.
    assert height == MAX_SOURCE_LONG_SIDE


def test_a_normal_photo_is_left_untouched():
    """On ne retouche pas ce qui n'a pas besoin de l'etre."""
    import io

    from PIL import Image

    from app.services.vto_service import _bounded

    buffer = io.BytesIO()
    Image.new("RGB", (1080, 1440), (200, 190, 180)).save(buffer, format="JPEG")
    data = buffer.getvalue()

    assert _bounded(data) is data


def test_the_probe_sends_what_the_app_sends():
    """La sonde envoyait les octets bruts du fichier.

    Ni redressement EXIF, ni bornage, ni normalisation de ratio : elle testait
    un chemin que le produit n'emprunte jamais, et son verdict ne prouvait rien
    sur lui. Sur la photo de reference, elle envoyait 1306x4080 la ou
    l'application envoie 1152x2048.
    """
    from pathlib import Path

    probe = Path(__file__).resolve().parents[3] / "scripts" / "probe_vto.py"
    source = probe.read_text(encoding="utf-8")

    assert "_bounded" in source, "the probe must apply the same aspect handling"
    assert "validate_image" in source, "the probe must apply the same EXIF handling"
    assert "service.generate(prepared" in source, "the probe must send the prepared bytes"
    assert "service.generate(photo.read_bytes()" not in source


async def test_a_failing_catalogue_piece_falls_back_to_another(client, flow):
    """Mesure en direct : `jacket_01` echoue la ou `jacket_02` reussit.

    Les deux passent tous nos controles — vraie photographie, personne dessus,
    definition correcte. Nous ne savons pas dire lesquelles echoueront, donc le
    produit essaie la suivante plutot que de rendre une erreur.
    """
    from app.integrations.youcam import set_providers
    from app.integrations.youcam.exceptions import YouCamProviderError
    from app.integrations.youcam.mock import LocalCompositeVTOService

    tried: list[str] = []

    class FailsOnTheFirstPiece(LocalCompositeVTOService):
        provider_name = "youcam_apparel_vto"

        async def generate(self, source_image, garment, *, source_mime="image/jpeg"):
            tried.append(garment.garment_id)
            if len(tried) == 1:
                raise YouCamProviderError(
                    "Provider task failed (error)",
                    detail="error_editing_failed",
                    provider_code="error_editing_failed",
                )
            return await super().generate(source_image, garment, source_mime=source_mime)

    set_providers(vto=FailsOnTheFirstPiece())
    session_id = await flow.session()
    await flow.moment(session_id)
    await flow.analyze(session_id)
    recommendation = await flow.one_change(session_id)

    response = await flow.vto(session_id)
    assert response.status_code == 201, response.text[:200]

    body = response.json()
    assert len(tried) == 2, f"expected exactly one fallback, got {tried}"
    assert tried[0] != tried[1]
    assert body["garment_id"] == tried[1], "the response must name the piece actually used"
    # La DECISION n'a pas bouge : seule la piece de la preuve a change.
    assert body["action"] == recommendation["action"]


async def test_the_fallback_is_tried_once_and_only_once(client, flow):
    """Deux echecs d'affilee signalent la photo, pas le vetement."""
    from app.integrations.youcam import set_providers
    from app.integrations.youcam.exceptions import YouCamProviderError

    tried: list[str] = []

    class AlwaysFails:
        provider_name = "youcam_apparel_vto"

        async def generate(self, source_image, garment, *, source_mime="image/jpeg"):
            tried.append(garment.garment_id)
            raise YouCamProviderError(
                "Provider task failed (error)",
                detail="error_editing_failed",
                provider_code="error_editing_failed",
            )

    set_providers(vto=AlwaysFails())
    session_id = await flow.session()
    await flow.moment(session_id)
    await flow.analyze(session_id)
    await flow.one_change(session_id)

    response = await flow.vto(session_id)
    assert response.status_code == 502
    assert len(tried) == 2, f"burned {len(tried)} credits looking for a needle"


async def test_a_users_own_piece_is_never_swapped(client, flow):
    """Il l'a choisie : on ne lui en substitue pas une autre."""
    from app.integrations.youcam import set_providers
    from app.integrations.youcam.exceptions import YouCamProviderError

    tried: list[str] = []

    class AlwaysFails:
        provider_name = "youcam_apparel_vto"

        async def generate(self, source_image, garment, *, source_mime="image/jpeg"):
            tried.append(garment.garment_id)
            raise YouCamProviderError(
                "Provider task failed (error)",
                detail="error_editing_failed",
                provider_code="error_editing_failed",
            )

    set_providers(vto=AlwaysFails())
    session_id = await flow.session()
    await flow.moment(session_id)
    await flow.analyze(session_id)
    await flow.one_change(session_id)

    upload = await client.post(
        "/api/v1/garments/upload",
        data={"session_id": session_id},
        files={"image": ("mine.jpg", garment_photo(), "image/jpeg")},
    )
    asset_id = upload.json()["id"]
    response = await client.post(
        "/api/v1/vto/generate",
        json={"session_id": session_id, "garment_asset_id": asset_id},
    )

    assert response.status_code == 502
    assert tried == [asset_id], "the user's piece was replaced by a catalogue one"


async def test_before_and_after_share_the_same_framing(client, flow, db):
    """Le comparateur doit opposer deux images qui ne different QUE par le vetement.

    Le « avant » servait la photo d'origine pendant que le « apres » venait de
    la photo preparee. Sur un cliche etire — complete sur les cotes avant envoi
    — les deux cadrages differaient : le « avant » paraissait zoome, et la
    difference affichee incluait un recadrage.
    """
    import io

    from PIL import Image
    from sqlalchemy import select

    from app.models.image_asset import ImageAsset

    # Une photo en bande, comme celle qui a revele le probleme.
    buffer = io.BytesIO()
    Image.new("RGB", (700, 2100), (150, 130, 120)).save(buffer, format="JPEG")
    strip = buffer.getvalue()

    session_id = await flow.session()
    await flow.moment(session_id)
    await client.post(
        "/api/v1/appearance/analyze",
        data={"session_id": session_id},
        files={"image": ("strip.jpg", strip, "image/jpeg")},
    )
    await flow.one_change(session_id)
    response = await flow.vto(session_id)
    assert response.status_code == 201

    detail = (await client.get(f"/api/v1/sessions/{session_id}")).json()
    before_url = detail["vto"]["before_image_url"]
    after_url = detail["vto"]["result_image_url"]

    shapes = []
    for url in (before_url, after_url):
        served = await client.get(url)
        assert served.status_code == 200
        with Image.open(io.BytesIO(served.content)) as image:
            shapes.append(image.width / image.height)

    assert abs(shapes[0] - shapes[1]) < 0.02, (
        f"before/after framings differ: {shapes[0]:.2f} vs {shapes[1]:.2f}"
    )


async def test_a_normal_photo_keeps_its_original_asset(client, flow, db):
    """On ne duplique pas une image qui n'avait pas besoin d'etre preparee."""
    from sqlalchemy import func, select

    from app.models.image_asset import ImageAsset
    from tests.conftest import make_image

    session_id = await flow.session()
    await flow.moment(session_id)
    await client.post(
        "/api/v1/appearance/analyze",
        data={"session_id": session_id},
        files={"image": ("look.jpg", make_image(width=1080, height=1440), "image/jpeg")},
    )
    await flow.one_change(session_id)
    await flow.vto(session_id)

    count = await db.scalar(
        select(func.count()).select_from(ImageAsset).where(
            ImageAsset.session_id == session_id, ImageAsset.kind == "input"
        )
    )
    assert count == 1, "a normal photo should not be stored twice"
