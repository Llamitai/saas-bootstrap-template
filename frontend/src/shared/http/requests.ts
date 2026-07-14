import { serverConfig } from "@/shared/config/server";

export { getCommonHeaders, isServer } from "@/shared/http/headers";

export const getBackendHostname = () => {
  return serverConfig.apiBaseUrl;
};
