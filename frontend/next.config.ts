import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const backendUrl =
  process.env.NEXT_PUBLIC_BACKEND_API_HOST ||
  process.env.BACKEND_API_HOST ||
  "http://localhost:8200";

const nextConfig: NextConfig = {
  output: "standalone",
  // Pin the workspace root to this directory (where next.config.ts lives).
  // Next infers the root by scanning up for lockfiles; if a dev machine has a
  // stray lockfile in a parent (e.g. ~/package-lock.json), it warns and may
  // pick the wrong root — which also breaks `output: "standalone"` file
  // tracing for a local build. `__dirname` is portable (it resolves to each
  // checkout's frontend dir), so no machine-specific path is hardcoded.
  outputFileTracingRoot: __dirname,
  transpilePackages: ["react-icons"],
  turbopack: {
    root: __dirname,
  },
  // Bump the proxy timeout for rewrite-proxied API requests that legitimately
  // need more than the default ~30s budget.
  experimental: {
    proxyTimeout: 5 * 60 * 1000,
  },
  webpack: (config) => {
    config.resolve.alias.canvas = false;
    return config;
  },
  async rewrites() {
    return {
      afterFiles: [
        {
          source: "/api/v1/:path*",
          destination: `${backendUrl}/v1/:path*`,
        },
      ],
      beforeFiles: [],
      fallback: [],
    };
  },
};

export default withNextIntl(nextConfig);
