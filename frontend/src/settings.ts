import { serverConfig } from "@/shared/config/server";

// Legacy compatibility export. New code should import from `@/shared/config`.
export const Settings = {
  apiBaseUrl: serverConfig.apiBaseUrl,
  version: serverConfig.version,
  apiKey: serverConfig.apiKey,
  isProd: serverConfig.isProd,
};
