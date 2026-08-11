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
