import axios from "axios";

import { serverConfig } from "@/shared/config/server";

// Server-side: direct to backend from BFF route handlers and server-only code.
export const serverHttp = axios.create({
  baseURL: `${serverConfig.apiBaseUrl}/v1`,
  timeout: 10000,
});
