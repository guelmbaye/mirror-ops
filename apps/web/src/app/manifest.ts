import type { MetadataRoute } from "next";

/**
 * Manifeste d'application. Épinglé à l'écran d'accueil, MIRROR OPS s'ouvre
 * directement sur le parcours — pas sur une barre d'adresse.
 */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Mirror Ops — one moment, one change",
    short_name: "Mirror Ops",
    description:
      "Contextual appearance decision engine. Know what to change before you change it.",
    start_url: "/",
    display: "standalone",
    background_color: "#f0f1f3",
    theme_color: "#f0f1f3",
    icons: [
      { src: "/icon.png", sizes: "512x512", type: "image/png" },
      { src: "/apple-icon.png", sizes: "180x180", type: "image/png" },
    ],
  };
}
