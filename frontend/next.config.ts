import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    // Increase proxy timeout for long-running AI requests
    proxyTimeout: 120000,
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
