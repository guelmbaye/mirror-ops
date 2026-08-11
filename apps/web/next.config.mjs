import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Les packages partagés sont du TypeScript brut : Next doit les transpiler.
  transpilePackages: ["@mirror-ops/types", "@mirror-ops/config"],
  // Image serveur légère : Next n'embarque que ce que l'application utilise.
  output: "standalone",
  experimental: {
    // Racine du monorepo, declaree explicitement.
    //
    // Sans elle, Next la DEDUIT — et selon la presence d'un fichier de verrou,
    // place `server.js` soit a la racine de `standalone/`, soit sous
    // `apps/web/`. Un Dockerfile ne peut pas parier sur une disposition
    // variable : le conteneur bouclait sur « Cannot find module server.js ».
    // Elle garantit aussi que packages/types et packages/config sont traces.
    outputFileTracingRoot: path.join(here, "../.."),
  },
  eslint: { ignoreDuringBuilds: true },
};

export default nextConfig;
