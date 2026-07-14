"use client";

import { useMemo } from "react";
import { CodeViewer } from "@/shared/ui/components/ui/code-viewer";

export type JsonViewerTheme = "default";

interface JsonViewerProps {
  /** Anything JSON-serialisable. Falls back to `String(value)` on cycles. */
  value: unknown;
  /** Reserved for future theme variants. Current theme follows light/dark CSS tokens. */
  theme?: JsonViewerTheme;
  /** Show the left gutter with line numbers (default `true`). */
  showLineNumbers?: boolean;
  /**
   * Filename for the download action (including `.json` extension).
   * When omitted, the download button is hidden.
   */
  downloadFileName?: string;
  className?: string;
}

export function JsonViewer({
  value,
  showLineNumbers = true,
  downloadFileName,
  className,
}: JsonViewerProps) {
  const code = useMemo(() => {
    return stringifyJsonLikeValue(value);
  }, [value]);

  return (
    <CodeViewer
      code={code}
      language="json"
      showLineNumbers={showLineNumbers}
      downloadFileName={downloadFileName}
      className={className}
    />
  );
}

function stringifyJsonLikeValue(value: unknown): string {
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
      try {
        return JSON.stringify(JSON.parse(value), null, 2);
      } catch {
        return value;
      }
    }
    return value;
  }

  try {
    return JSON.stringify(value, null, 2) ?? "null";
  } catch {
    return String(value);
  }
}
