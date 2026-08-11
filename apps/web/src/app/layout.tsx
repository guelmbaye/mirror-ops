import type { Metadata, Viewport } from "next";

import "./globals.css";

export const metadata: Metadata = {
  // Sert à résoudre les URLs absolues des images sociales.
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"),
  title: "Mirror Ops — one moment, one change",
  description:
    "Mirror Ops is a contextual appearance decision engine. It identifies the one appearance intervention worth making for a specific moment — and proves it visually before you act.",
  applicationName: "Mirror Ops",
  openGraph: {
    title: "Mirror Ops — one moment, one change",
    description:
      "Know what to change before you change it. Mirror Ops finds the one appearance change worth making for the moment you're in.",
    siteName: "Mirror Ops",
    type: "website",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#f0f1f3",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        {/* Les familles sont chargées à distance mais chaque rôle a une pile de
            repli explicite dans globals.css : hors ligne, la mise en page tient. */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700&family=Fraunces:opsz,wght@9..144,500;9..144,600&family=JetBrains+Mono:wght@400;500;700&display=swap"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
