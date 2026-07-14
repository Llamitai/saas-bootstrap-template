import { getLLMText } from "@/llms/mdx";
import { source } from "@/lib/source";

export async function loader() {
  const pages = await Promise.all(source.getPages().map(getLLMText));

  return new Response(pages.join("\n\n"), {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
    },
  });
}
