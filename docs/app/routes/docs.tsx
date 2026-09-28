import browserCollections from "collections/browser";
import { useFumadocsLoader } from "fumadocs-core/source/client";
import { DocsLayout } from "fumadocs-ui/layouts/notebook";
import {
  DocsBody,
  DocsDescription,
  DocsPage,
  DocsTitle,
  MarkdownCopyButton,
  ViewOptionsPopover,
} from "fumadocs-ui/layouts/notebook/page";
import { data } from "react-router";
import { OpenAPIPage } from "@/components/api-page";
import { getMDXComponents } from "@/components/mdx";
import { baseOptions } from "@/lib/layout.shared";
import { appName, getPageMarkdownUrl } from "@/lib/shared";
import { source } from "@/lib/source";
import { getRepoUrl } from "../../lib/repo-links";
import type { Route } from "./+types/docs";

export async function loader({ params }: Route.LoaderArgs) {
  const slugs = (params["*"] ?? "").split("/").filter(Boolean);
  const page = source.getPage(slugs);

  if (!page) {
    throw data("Página no encontrada", { status: 404 });
  }

  const pageTree = await source.serializePageTree(source.getPageTree());
  const common = {
    title: page.data.title ?? appName,
    description: page.data.description ?? "",
    pageTree,
  };

  if (page.type === "openapi") {
    return {
      ...common,
      type: "openapi" as const,
      props: page.data.getOpenAPIPageProps(),
    };
  }

  const repoUrl = getRepoUrl();
  return {
    ...common,
    type: "docs" as const,
    path: page.path,
    markdownUrl: getPageMarkdownUrl(page).url,
    sourceUrl: repoUrl
      ? `${repoUrl}/blob/HEAD/docs/content/docs/${page.path}`
      : null,
  };
}

export async function clientLoader({ serverLoader }: Route.ClientLoaderArgs) {
  const loaded = await serverLoader();
  if (loaded.type === "docs") {
    await clientContent.preload(loaded.path);
  }
  return loaded;
}

export function meta({ loaderData }: Route.MetaArgs) {
  if (!loaderData) {
    return [{ title: `No encontrado | ${appName} Docs` }];
  }

  return [
    { title: `${loaderData.title} | ${appName} Docs` },
    { name: "description", content: loaderData.description },
  ];
}

interface ContentProps {
  markdownUrl: string;
  sourceUrl: string | null;
}

const clientContent = browserCollections.docs.createClientLoader<ContentProps>({
  id: "docs",
  component({ toc, frontmatter, default: Mdx }, { markdownUrl, sourceUrl }) {
    return (
      <DocsPage toc={toc} tableOfContent={{ style: "clerk" }}>
        <DocsTitle>{frontmatter.title}</DocsTitle>
        {frontmatter.description ? (
          <DocsDescription>{frontmatter.description}</DocsDescription>
        ) : null}
        <div className="-mt-4 flex flex-row flex-wrap items-center gap-2 border-b pb-6">
          <MarkdownCopyButton markdownUrl={markdownUrl} />
          <ViewOptionsPopover
            markdownUrl={markdownUrl}
            githubUrl={sourceUrl ?? undefined}
          />
        </div>
        <DocsBody>
          <Mdx components={getMDXComponents()} />
        </DocsBody>
      </DocsPage>
    );
  },
});

// The client loader exposes a hook, so it lives in its own component: the
// route renders it only for Markdown pages and hooks keep a stable order.
function DocsContent({ path, ...props }: ContentProps & { path: string }) {
  return clientContent.useContent(path, props);
}

export default function DocsRoute({ loaderData }: Route.ComponentProps) {
  const page = useFumadocsLoader(loaderData);
  const { nav, ...base } = baseOptions();

  return (
    <DocsLayout
      {...base}
      nav={{ ...nav, mode: "top" }}
      tabMode="navbar"
      sidebar={{ defaultOpenLevel: 1 }}
      tree={page.pageTree}
    >
      {page.type === "openapi" ? (
        <DocsPage full>
          <DocsTitle>{page.title}</DocsTitle>
          {page.description ? (
            <DocsDescription>{page.description}</DocsDescription>
          ) : null}
          <DocsBody>
            <OpenAPIPage {...page.props} />
          </DocsBody>
        </DocsPage>
      ) : (
        <DocsContent
          path={page.path}
          markdownUrl={page.markdownUrl}
          sourceUrl={page.sourceUrl}
        />
      )}
    </DocsLayout>
  );
}
