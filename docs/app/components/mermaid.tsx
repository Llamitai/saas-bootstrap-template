import { useEffect, useId, useState } from "react";

interface MermaidProps {
  chart?: string;
  children?: string;
}

function isDarkTheme() {
  if (typeof document === "undefined") {
    return false;
  }

  return document.documentElement.classList.contains("dark");
}

export function Mermaid({ chart, children }: MermaidProps) {
  const id = useId().replace(/:/g, "");
  const source = (chart ?? children ?? "").trim();
  const [svg, setSvg] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [dark, setDark] = useState(false);

  useEffect(() => {
    setDark(isDarkTheme());
    const observer = new MutationObserver(() => {
      setDark(isDarkTheme());
    });

    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class", "data-theme"],
    });

    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function renderMermaid() {
      if (!source) {
        setSvg("");
        return;
      }

      try {
        const mermaid = (await import("mermaid")).default;

        mermaid.initialize({
          startOnLoad: false,
          securityLevel: "strict",
          theme: dark ? "dark" : "neutral",
          fontFamily: "Geist, ui-sans-serif, system-ui, sans-serif",
        });

        const rendered = await mermaid.render(`mermaid-${id}`, source);

        if (!cancelled) {
          setSvg(rendered.svg);
          setError(null);
        }
      } catch (reason) {
        if (!cancelled) {
          setError(
            reason instanceof Error ? reason.message : "Diagrama inválido"
          );
        }
      }
    }

    void renderMermaid();

    return () => {
      cancelled = true;
    };
  }, [id, source, dark]);

  if (error) {
    return (
      <pre className="mermaid-frame text-sm text-red-600 dark:text-red-400">
        {error}
      </pre>
    );
  }

  return (
    <div
      className="mermaid-frame"
      // biome-ignore lint/security/noDangerouslySetInnerHtml: SVG produced by mermaid.render with securityLevel "strict", which sanitizes the output.
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
