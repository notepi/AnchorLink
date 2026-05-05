import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // TypeScript 配置
  typescript: {
    ignoreBuildErrors: false,
  },
};

export default nextConfig;