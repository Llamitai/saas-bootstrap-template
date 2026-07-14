import type { MDXComponents } from "mdx/types";
import { Children, isValidElement, type ComponentProps } from "react";
import defaultMdxComponents from "fumadocs-ui/mdx";
import * as AccordionComponents from "fumadocs-ui/components/accordion";
import * as StepsComponents from "fumadocs-ui/components/steps";
import * as TabsComponents from "fumadocs-ui/components/tabs";
import { TypeTable } from "fumadocs-ui/components/type-table";
import { Mermaid } from "@/components/mermaid";

function Pre(props: ComponentProps<"pre">) {
  const child = Children.only(props.children);

  if (
    isValidElement<{ className?: string; children?: string }>(child) &&
    child.props.className?.includes("language-mermaid")
  ) {
    return <Mermaid chart={String(child.props.children ?? "")} />;
  }

  const DefaultPre = defaultMdxComponents.pre ?? "pre";
  return <DefaultPre {...props} />;
}

export function getMDXComponents(components?: MDXComponents): MDXComponents {
  return {
    ...defaultMdxComponents,
    ...TabsComponents,
    ...StepsComponents,
    ...AccordionComponents,
    TypeTable,
    Mermaid,
    pre: Pre,
    ...components,
  };
}
