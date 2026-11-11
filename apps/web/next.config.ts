import type { NextConfig } from 'next';
import createNextIntlPlugin from 'next-intl/plugin';

const config: NextConfig = {
  poweredByHeader: false,
  env: {
    NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000',
  },
};
export default createNextIntlPlugin()(config);
