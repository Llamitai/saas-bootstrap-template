export const config = {
  apiHost: import.meta.env.VITE_API_HOST ?? "http://localhost:8200",
  docsRequireAuth: import.meta.env.VITE_DOCS_REQUIRE_AUTH === "true",
};
