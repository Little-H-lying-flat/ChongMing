import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    // Increase proxy timeout to 300s for long-running AI multi-agent requests
    proxyTimeout: 300000,
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
