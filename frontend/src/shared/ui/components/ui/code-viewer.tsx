"use client";

import { Download } from "lucide-react";
import type { CSSProperties } from "react";
import { useCallback } from "react";
import { PrismLight as SyntaxHighlighter } from "react-syntax-highlighter";
import go from "react-syntax-highlighter/dist/esm/languages/prism/go";
import javascript from "react-syntax-highlighter/dist/esm/languages/prism/javascript";
import json from "react-syntax-highlighter/dist/esm/languages/prism/json";
import php from "react-syntax-highlighter/dist/esm/languages/prism/php";
import python from "react-syntax-highlighter/dist/esm/languages/prism/python";
import typescript from "react-syntax-highlighter/dist/esm/languages/prism/typescript";

import { cn } from "@/shared/lib/utils";

SyntaxHighlighter.registerLanguage("go", go);
SyntaxHighlighter.registerLanguage("javascript", javascript);
SyntaxHighlighter.registerLanguage("json", json);
SyntaxHighlighter.registerLanguage("php", php);
SyntaxHighlighter.registerLanguage("python", python);
SyntaxHighlighter.registerLanguage("typescript", typescript);

export type CodeViewerLanguage =
  | "go"
  | "javascript"
  | "json"
  | "php"
  | "python"
  | "typescript";

const PROJECT_CODE_STYLE = {
  'code[class*="language-"]': {
    color: "var(--code-block-fg)",
    background: "var(--code-block-bg)",
    fontFamily:
      "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, monospace",
    textShadow: "none",
    whiteSpace: "pre",
  },
  'pre[class*="language-"]': {
    color: "var(--code-block-fg)",
    background: "var(--code-block-bg)",
    fontFamily:
      "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, monospace",
    textShadow: "none",
  },
  comment: {
    color: "var(--code-token-muted)",
  },
  punctuation: {
    color: "var(--code-token-punctuation)",
  },
  property: {
    color: "var(--code-token-property)",
  },
  string: {
    color: "var(--code-token-string)",
  },
  number: {
    color: "var(--code-token-number)",
  },
  boolean: {
    color: "var(--code-token-boolean)",
  },
  null: {
    color: "var(--code-token-null)",
  },
  keyword: {
    color: "var(--code-token-boolean)",
  },
  function: {
    color: "var(--code-token-property)",
  },
  operator: {
    color: "var(--code-token-punctuation)",
  },
  variable: {
    color: "var(--code-block-fg)",
  },
  builtin: {
    color: "var(--code-token-number)",
  },
} satisfies Record<string, CSSProperties>;

interface CodeViewerProps {
  code: string;
  language: CodeViewerLanguage;
  showLineNumbers?: boolean;
  downloadFileName?: string;
  className?: string;
  maxHeightClassName?: string;
}

export function CodeViewer({
  code,
  language,
  showLineNumbers = true,
  downloadFileName,
  className,
  maxHeightClassName,
}: CodeViewerProps) {
  const handleDownload = useCallback(() => {
    if (!downloadFileName) return;
    const blob = new Blob([code], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = downloadFileName;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }, [code, downloadFileName]);

  return (
    <div
      className={cn(
        "code-block-surface relative overflow-hidden rounded-lg",
        "[&_pre]:!m-0",
        "[&_pre]:![scrollbar-width:thin]",
        "[&_pre]:[scrollbar-color:transparent_transparent]",
        "hover:[&_pre]:[scrollbar-color:color-mix(in_oklab,var(--muted-foreground)_35%,transparent)_transparent]",
        "[&_pre::-webkit-scrollbar]:h-1.5 [&_pre::-webkit-scrollbar]:w-1.5",
        "[&_pre::-webkit-scrollbar-track]:bg-transparent",
        "[&_pre::-webkit-scrollbar-thumb]:rounded-full [&_pre::-webkit-scrollbar-thumb]:bg-transparent",
        "[&_pre::-webkit-scrollbar-thumb]:transition-colors [&_pre::-webkit-scrollbar-thumb]:duration-200",
        "hover:[&_pre::-webkit-scrollbar-thumb]:bg-muted-foreground/30",
        "[&_pre::-webkit-scrollbar-thumb:hover]:bg-muted-foreground/60",
        maxHeightClassName,
        className
      )}
    >
      {downloadFileName ? (
        <button
          type="button"
          onClick={handleDownload}
          title={`Descargar ${downloadFileName}`}
          aria-label={`Descargar ${downloadFileName}`}
          className={cn(
            "absolute top-2 right-2 z-10 inline-flex h-7 w-7 cursor-pointer items-center justify-center rounded-lg",
            "border border-[var(--code-block-border)] bg-card/85 text-muted-foreground backdrop-blur-sm",
            "transition-colors hover:bg-md3-muted hover:text-foreground",
            "dark:border-white/10 dark:bg-white/5 dark:text-zinc-300 dark:hover:bg-white/10 dark:hover:text-white",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
          )}
        >
          <Download className="h-3.5 w-3.5" aria-hidden />
        </button>
      ) : null}

      <SyntaxHighlighter
        language={language}
        style={PROJECT_CODE_STYLE}
        showLineNumbers={showLineNumbers}
        wrapLongLines={false}
        lineNumberStyle={{
          minWidth: "2.5em",
          paddingRight: "1em",
          color: "var(--code-line-number)",
          userSelect: "none",
          textAlign: "right",
        }}
        customStyle={{
          margin: 0,
          padding: "0.875rem 1rem",
          paddingRight: downloadFileName ? "3rem" : "1rem",
          background: "var(--code-block-bg)",
          color: "var(--code-block-fg)",
          fontSize: "12px",
          lineHeight: 1.55,
        }}
        codeTagProps={{
          style: {
            fontFamily:
              "var(--font-geist-mono), ui-monospace, SFMono-Regular, Menlo, monospace",
          },
        }}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  );
}
