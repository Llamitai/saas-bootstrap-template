"use client";

import { motion, useReducedMotion } from "motion/react";

import { cn } from "@/shared/lib/utils";
import { useSidebar } from "@/shared/ui/sidebar";

/**
 * DESIGN.md §6 keeps motion restrained: no bouncy, physics-based, or
 * overshooting transitions. The active-indicator slide is a
 * "Spatial transition (150–300ms ease-out)", so the shared-layout pill moves
 * on the calm `--ease-emphasized` curve, not a spring engine.
 */
const SLIDE = { duration: 0.25, ease: [0.2, 0, 0, 1] } as const;

/**
 * The active-destination pill. Rendered as the first child of the active
 * `<li>` (which is `position: relative`); it fills the row behind the icon and
 * label. Because exactly one nav item is active at a time, exactly one element
 * owns `layoutId`, so `motion` treats it as the same element relocating and
 * springs it between destinations — across both nav groups, since `layoutId`
 * is global (kept coordinated by the parent `<LayoutGroup>`).
 *
 * In the collapsed rail the sidebar width is itself mid-transition, which
 * fights shared-layout projection, so there we drop to a plain (non-animated)
 * pill that simply appears on the active icon.
 */
export function NavActiveIndicator({ className }: { className?: string }) {
  const { state } = useSidebar();
  const reduceMotion = useReducedMotion();

  const base = cn(
    "bg-sidebar-accent pointer-events-none absolute inset-0 -z-10 rounded-lg",
    className
  );

  if (state === "collapsed") {
    return <span aria-hidden className={base} />;
  }

  return (
    <motion.span
      aria-hidden
      layoutId="sidebar-active-pill"
      className={base}
      transition={reduceMotion ? { duration: 0 } : SLIDE}
    />
  );
}
