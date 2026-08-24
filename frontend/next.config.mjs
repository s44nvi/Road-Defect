// The backend has no CORS middleware configured, and it should not be
// modified from the frontend. Requests to the default `/api` boundary
// (see lib/api.ts) are proxied server-side to the backend origin below,
// so the browser only ever talks same-origin and never needs CORS.
//
// BACKEND_ORIGIN is a server-only env var (never sent to the client bundle,
// unlike NEXT_PUBLIC_* vars) so a temporary tunnel URL never ends up in
// shipped source. Set it in frontend/.env.local for local development.
const backendOrigin = process.env.BACKEND_ORIGIN ?? "http://localhost:8000";

/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendOrigin}/:path*`,
      },
    ];
  },
};

export default nextConfig;
