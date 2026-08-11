# Notice — third-party resources

## Code

MIRROR OPS is distributed under the MIT licence (see `LICENSE`).

## Third-party services

The product calls the **YouCam / Perfect Corp** APIs (Skin AI, Apparel VTO).
Those services are governed by their own terms of use. No key is included in
this repository: configuration happens through environment variables,
server-side only.

## Catalogue visuals

The images in `apps/api/app/assets/garments/` are **generated programmatically**
by this project: flat shapes of a few colours, containing no third-party
content. They serve as an offline fallback and are unsuitable for a real
try-on — see `scripts/import_garments.py` to replace them.

If you import photographs, make sure you hold the rights. The **Clothing
dataset** (`agrigorev/clothing-dataset-full`) is published under CC0 and is
suitable for public distribution.

## Fonts

Archivo, Fraunces and JetBrains Mono are loaded from Google Fonts and
distributed under the SIL Open Font License. No font file is redistributed in
this repository.

## Logo

`MIRROR OPS` and its symbol belong to their author and are not covered by the
MIT licence applying to the code.
