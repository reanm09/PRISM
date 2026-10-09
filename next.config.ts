import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  reactStrictMode: true,
  distDir: process.env.PRISM_LOCAL_MODE === '1' ? '.next-prism-local' : '.next',
};

export default nextConfig;
