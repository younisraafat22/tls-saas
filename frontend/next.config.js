/** @type {import('next').NextConfig} */
const nextConfig = {
  // Docker uses Next's standalone server bundle. Vercel provides its own
  // serverless packaging and must build without the standalone override.
  ...(process.env.VERCEL ? {} : { output: 'standalone' }),
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
    NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000',
  },
};

module.exports = nextConfig;
