import { publicConfig } from "@/shared/config/public";

// Server-only configuration. Do not import this from client components.
export const serverConfig = {
  apiBaseUrl:
    process.env.NEXT_PUBLIC_BACKEND_API_HOST ||
    process.env.BACKEND_API_HOST ||
    "http://localhost:8200",
  apiKey: process.env.BACKEND_API_KEY || "",
  cfAccessClientId: process.env.CF_ACCESS_CLIENT_ID || "",
  cfAccessClientSecret: process.env.CF_ACCESS_CLIENT_SECRET || "",
  googleClientId: process.env.GOOGLE_CLIENT_ID || "",
  // Public origin for OAuth redirects; falls back to the request origin when unset.
  appUrl: process.env.NEXT_PUBLIC_APP_URL || "",
  ...publicConfig,
};
