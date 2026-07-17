import type { NextConfig } from "next";

const isProduction = process.env.NODE_ENV === "production";
const requiredProductionEnv = [
  "NEXT_PUBLIC_CHAT_API_URL",
  "PRIVACY_NOTICE_VERSION",
  "PRIVACY_NOTICE_ES",
  "PRIVACY_NOTICE_EN",
  "WIDGET_FRAME_ANCESTORS",
] as const;

if (isProduction) {
  for (const name of requiredProductionEnv) {
    if (!process.env[name]?.trim()) throw new Error(`${name} is required in production`);
  }
  if (!process.env.NEXT_PUBLIC_CHAT_API_URL?.startsWith("https://")) {
    throw new Error("NEXT_PUBLIC_CHAT_API_URL must use HTTPS in production");
  }
  if (process.env.PRIVACY_NOTICE_VERSION?.startsWith("development-")) {
    throw new Error("PRIVACY_NOTICE_VERSION must identify the approved notice");
  }
}

const frameAncestors = process.env.WIDGET_FRAME_ANCESTORS ?? "'self' http://localhost:3000";
if (/[;\r\n]/.test(frameAncestors)) throw new Error("WIDGET_FRAME_ANCESTORS is invalid");
if (isProduction) {
  for (const source of frameAncestors.split(/\s+/)) {
    if (source === "'self'") continue;
    try {
      const parsed = new URL(source);
      if (parsed.protocol !== "https:" || parsed.origin !== source) throw new Error();
    } catch {
      throw new Error("WIDGET_FRAME_ANCESTORS must contain only 'self' and HTTPS origins");
    }
  }
}

const isDev = process.env.NODE_ENV === "development";
const generalCsp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self'",
  "connect-src 'self'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const commonHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
  },
  ...(isProduction
    ? [{ key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" }]
    : []),
];

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          ...commonHeaders,
          {
            key: "Content-Security-Policy",
            value: generalCsp,
          },
        ],
      },
      {
        source: "/widget",
        headers: [
          ...commonHeaders,
          {
            key: "Content-Security-Policy",
            value: `object-src 'none'; base-uri 'self'; form-action 'none'; frame-ancestors ${frameAncestors}`,
          },
          { key: "Cache-Control", value: "no-store" },
        ],
      },
    ];
  },
};

export default nextConfig;
