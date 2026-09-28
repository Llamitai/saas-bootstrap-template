import { data } from "react-router";
import { docsLlms, source } from "@/lib/source";
import type { Route } from "./+types/mdx";

// `/llms.mdx/docs/<slugs>/content.md` returns one page as Markdown.
export async function loader({ params }: Route.LoaderArgs) {
  const slugs = (params["*"] ?? "").split("/").filter(Boolean);
  if (slugs.pop() !== "content.md") {
    throw data("Página no encontrada", { status: 404 });
  }

  const page = source.getPage(slugs);
  if (!page) {
    throw data("Página no encontrada", { status: 404 });
  }

  return new Response(await docsLlms.page(page), {
    headers: { "Content-Type": "text/markdown; charset=utf-8" },
  });
}
