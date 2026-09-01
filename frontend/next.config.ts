import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */

  // Next.js blocks JS bundles and HMR by default from any origin other than
  // localhost/127.0.0.1 — the page renders but nothing is interactive. Needed
  // for testing on a phone over the LAN IP or a trycloudflare.com tunnel. See
  // README's "Testing on a phone" section. Add your own LAN IP if it differs.
  allowedDevOrigins: ["*.trycloudflare.com", "192.168.1.4"],
};

export default nextConfig;
