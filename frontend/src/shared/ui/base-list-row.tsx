"use client";

import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/shared/lib/utils";

/**
 * Shared styling for row-style cards (fields, validation rules, etc.):
 * - Consistent height via py-2.5
 * - Subtle bottom border between rows
 * - Hover highlight
 * - Horizontal layout with gap-2
 *
 * Wrap a list in <BaseListContainer> to get the rounded + bordered look.
 */
interface BaseListRowProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

export function BaseListRow({
  children,
  className,
  ...props
}: BaseListRowProps) {
  return (
    <div
      {...props}
      className={cn(
        "group flex items-center gap-2 border-b border-border/50 bg-card px-3 py-2.5 transition-colors hover:bg-muted/30",
        className
      )}
    >
      {children}
    </div>
  );
}

interface BaseListContainerProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

export function BaseListContainer({
  children,
  className,
  ...props
}: BaseListContainerProps) {
  return (
    <div
      {...props}
      className={cn(
        "overflow-hidden rounded-lg bg-card ring-1 ring-border/70 [&>*:last-child]:border-b-0",
        className
      )}
    >
      {children}
    </div>
  );
}
