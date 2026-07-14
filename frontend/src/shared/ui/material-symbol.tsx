import type { CSSProperties } from "react";

import { cn } from "@/shared/lib/utils";

export interface MaterialSymbolProps {
  /**
   * Ligature name of the icon, e.g. `"settings"`. Must be a valid token from
   * the Material Symbols Rounded set (https://fonts.google.com/icons).
   */
  name: string;
  /**
   * `FILL` axis, 0..1. 0 is outlined, 1 is solid. Transitions smoothly (the
   * base `.material-symbols-rounded` rule animates `font-variation-settings`),
   * which is the MD3 Expressive outlined→filled morph for active items.
   */
  fill?: number;
  /** `wght` axis, 100..700. */
  weight?: number;
  /** `GRAD` axis, -50..200. Subtle emphasis without changing glyph size. */
  grade?: number;
  /** `opsz` axis + rendered glyph size in px. */
  size?: number;
  className?: string;
  style?: CSSProperties;
  "aria-hidden"?: boolean;
}

/**
 * Renders a single Material Symbols Rounded glyph as a `<span>` ligature.
 * The variable-font axes are driven through inline `font-variation-settings`
 * so `fill`/`weight` can animate. The font itself is loaded once via the
 * stylesheet `<link>` in the root layout.
 */
export function MaterialSymbol({
  name,
  fill = 0,
  weight = 400,
  grade = 0,
  size = 24,
  className,
  style,
  "aria-hidden": ariaHidden = true,
}: MaterialSymbolProps) {
  return (
    <span
      aria-hidden={ariaHidden}
      className={cn("material-symbols-rounded", className)}
      style={{
        fontSize: size,
        fontVariationSettings: `'FILL' ${fill}, 'wght' ${weight}, 'GRAD' ${grade}, 'opsz' ${size}`,
        ...style,
      }}
    >
      {name}
    </span>
  );
}
