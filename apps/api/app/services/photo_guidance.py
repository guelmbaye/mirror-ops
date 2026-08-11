"""Traduire un code d'erreur provider en consigne exploitable.

Doc 03 §16 : un etat d'echec donne une direction, jamais une humeur. « We
couldn't complete the visual preview » ne dit rien de ce qu'il faut corriger,
alors que le provider nomme precisement le probleme — pose non detectee,
plusieurs personnes, cadrage inadapte.

Ces messages s'adressent a quelqu'un qui se prepare, pas a un integrateur : ils
disent quoi refaire, pas ce qui a echoue.
"""

from __future__ import annotations

#: Consignes par code d'erreur YouCam.
PHOTO_GUIDANCE: dict[str, str] = {
    "error_pose": "We couldn't read your posture. Stand facing the camera, full body in frame.",
    "error_no_shoulder": "We need to see your shoulders — step back a little.",
    "error_multiple_people": "We can only work with one person in the photo.",
    "error_no_face": "We couldn't find a face in that photo.",
    "error_face_parsing": "We couldn't read your face clearly. Try better, more even light.",
    "error_large_face_angle": "Look straight at the camera rather than to the side.",
    "error_src_face_too_small": "Move a bit closer, or take the photo in better light.",
    "error_src_face_out_of_bound": "Keep your whole face inside the frame.",
    "error_unsupport_ratio": "That photo's shape isn't supported. A portrait shot works best.",
    "error_below_min_image_size": "That photo is too small. Take a new one at full resolution.",
    "error_exceed_max_image_size": "That photo is too large. Take a new one at normal resolution.",
    "exceed_max_filesize": "That photo is over the size limit. Take a new one.",
    "error_lighting_dark": "It's too dark. Move somewhere brighter and try again.",
    "error_decode_image": "We couldn't read that file. Use a JPEG or PNG.",
    "error_download_image": "We couldn't read that file. Try taking the photo again.",
    "error_nsfw_content_detected": "We can't work with that photo.",
    # Le rendu a echoue : ce n'est pas forcement la photo, c'est souvent le
    # vetement de reference qui n'est pas exploitable.
    "error_editing_failed": "We couldn't build that preview. Try another piece.",
}

#: Consigne par defaut quand le code est inconnu ou absent.
DEFAULT_PHOTO_GUIDANCE = "We need a clearer view of your look."


def guidance_for(provider_code: str | None, fallback: str = DEFAULT_PHOTO_GUIDANCE) -> str:
    if not provider_code:
        return fallback
    return PHOTO_GUIDANCE.get(provider_code, fallback)
