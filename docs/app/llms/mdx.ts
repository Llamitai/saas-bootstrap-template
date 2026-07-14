import { data } from "react-router";
import type { Route } from "./+types/mdx";
import { source } from "@/lib/source";

export async function getLLMText(page: (typeof source)["$inferPage"]) {
  const processed = await page.data.getText("processed");
  return `# ${page.data.title} (${page.url})\n\n${processed}`;
}

export async function loader({ params }: Route.LoaderArgs) {
  const slugs = (params["*"] ?? "").split("/").filter(Boolean);
  const page = source.getPage(slugs);

  if (!page) {
    throw data("Página no encontrada", { status: 404 });
  }

  return new Response(await getLLMText(page), {
    headers: {
      "Content-Type": "text/markdown; charset=utf-8",
    },
  });
}
