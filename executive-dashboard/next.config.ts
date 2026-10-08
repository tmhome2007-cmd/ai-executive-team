import type { NextConfig } from "next";

// Keep browser egress aligned with the API URL embedded in the client build.
const apiUrl = new URL(process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000");
if (!["http:", "https:"].includes(apiUrl.protocol) || apiUrl.username || apiUrl.password) {
  throw new Error("NEXT_PUBLIC_API_BASE must be an HTTP(S) URL without credentials");
}

const isDevelopment = process.env.NODE_ENV !== "production";
const scriptSrc = isDevelopment
  ? "script-src 'self' 'unsafe-inline' 'unsafe-eval'"
  : "script-src 'self' 'unsafe-inline'";

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "no-referrer" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=(), usb=()" },
  {
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      "base-uri 'none'",
      "form-action 'self'",
      "frame-ancestors 'none'",
      "object-src 'none'",
      "img-src 'self' blob: data:",
      "font-src 'self' data:",
      "style-src 'self' 'unsafe-inline'",
      scriptSrc,
      `connect-src 'self' ${apiUrl.origin}`,
    ].join("; "),
  },
];

const nextConfig: NextConfig = {
  poweredByHeader: false,
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: securityHeaders,
      },
    ];
  },
};

export default nextConfig;
