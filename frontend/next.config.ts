import path from "node:path";

import type { NextConfig } from "next";

const backendUrl = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // The repo root has its own package-lock.json (for `npm run dev`); pin the app root here.
  turbopack: { root: path.join(__dirname) },
  // Proxy /api/* to FastAPI so the browser talks to one origin (no CORS setup needed).
  rewrites() {
    return [{ source: "/api/:path*", destination: `${backendUrl}/api/:path*` }];
  },
};

export default nextConfig;
