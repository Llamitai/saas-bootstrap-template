export const publicConfig = {
  version: process.env.NEXT_PUBLIC_VERSION || "1.0.0",
  isProd: process.env.NODE_ENV === "production",
};
