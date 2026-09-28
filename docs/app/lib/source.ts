import { docs } from "collections/server";
import { llms, loader } from "fumadocs-core/source";
import { lucideIconsPlugin } from "fumadocs-core/source/lucide-icons";
import { openapi, openapiPages } from "../../lib/openapi";
import { docsRoute } from "./shared";

// Server-only: route loaders use it; components read content via collections/browser.
export const source = loader(
  {
    docs: docs.toFumadocsSource(),
    openapi: await openapi.staticSource(openapiPages),
  },
  {
    baseUrl: docsRoute,
    plugins: [lucideIconsPlugin(), openapi.loaderPlugin()],
  }
);

export type DocsPage = (typeof source)["$inferPage"];

export const docsLlms = llms(source, {
  renderPage: async (page) => {
    if (page.type === "openapi") {
      return `# ${page.data.title} (${page.url})\n\n\`\`\`json\n${JSON.stringify(page.data.getSchema().bundled, null, 2)}\n\`\`\``;
    }
    return `# ${page.data.title} (${page.url})\n\n${await page.data.getText("processed")}`;
  },
});
