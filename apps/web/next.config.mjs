/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Les packages partagés sont du TypeScript brut : Next doit les transpiler.
  transpilePackages: ["@mirror-ops/types", "@mirror-ops/config"],
  // Image serveur légère : Next n'embarque que ce que l'application utilise.
  output: "standalone",
  eslint: { ignoreDuringBuilds: true },
};

export default nextConfig;
