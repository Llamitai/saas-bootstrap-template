import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  Clock3,
  Info,
  Loader2,
  type LucideIcon,
  XCircle,
} from "lucide-react";
import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/shared/lib/utils";
import { Badge } from "@/shared/ui/badge";

export type StatusBadgeTone =
  | "neutral"
  | "info"
  | "processing"
  | "success"
  | "warning"
  | "destructive";

export type StatusBadgeSize = "xs" | "sm" | "md" | "lg";

type BadgeProps = ComponentProps<typeof Badge>;

export interface StatusBadgeProps
  extends Omit<BadgeProps, "children" | "variant"> {
  children?: ReactNode;
  status?: string | null;
  tone?: StatusBadgeTone;
  size?: StatusBadgeSize;
  icon?: LucideIcon | "auto" | null;
  loading?: boolean;
}

const toneClassName: Record<StatusBadgeTone, string> = {
  neutral: "border-border bg-muted text-muted-foreground",
  info: "border-[var(--md3-info)]/20 bg-[var(--md3-info-soft)] text-[var(--md3-info)]",
  processing: "border-primary/20 bg-accent text-accent-foreground",
  success: "border-success/25 bg-success/10 text-success-deep",
  warning: "border-warning/30 bg-warning/10 text-warning-deep",
  destructive: "border-destructive/25 bg-destructive/10 text-destructive-deep",
};

const sizeClassName: Record<StatusBadgeSize, string> = {
  xs: "h-5 gap-1 px-1.5 text-[10px] [&>svg]:!size-3",
  sm: "h-6 gap-1.5 px-2 text-[11px] [&>svg]:!size-3.5",
  md: "h-7 gap-1.5 px-2.5 text-xs [&>svg]:!size-3.5",
  lg: "h-9 gap-1.5 px-3.5 text-sm [&>svg]:!size-4",
};

const autoIcon: Record<StatusBadgeTone, LucideIcon> = {
  neutral: CircleDashed,
  info: Info,
  processing: Clock3,
  success: CheckCircle2,
  warning: AlertTriangle,
  destructive: XCircle,
};

export function statusBadgeToneForValue(
  status: string | null | undefined
): StatusBadgeTone {
  const value = (status ?? "").toLowerCase();

  if (/(fail|error|reject|invalid|blocked|revoked|expired)/.test(value)) {
    return "destructive";
  }
  if (/(warning|partial|needs|review|clarif|flag|limit|due|qa)/.test(value)) {
    return "warning";
  }
  if (
    /(process|index|pending|queue|sync|running|receiv|upload|delivering)/.test(
      value
    )
  ) {
    return "processing";
  }
  if (
    /(ready|active|enabled|done|complete|success|live|approved|verified|resolved|paid|healthy|ok|delivered)/.test(
      value
    )
  ) {
    return "success";
  }
  if (/(info|notice|event|sent|delivered)/.test(value)) {
    return "info";
  }

  return "neutral";
}

export function StatusBadge({
  children,
  status,
  tone,
  size = "md",
  icon = null,
  loading = false,
  className,
  ...props
}: StatusBadgeProps) {
  const resolvedTone = tone ?? statusBadgeToneForValue(status);
  const Icon = loading
    ? Loader2
    : icon === "auto"
      ? autoIcon[resolvedTone]
      : icon;
  const label = children ?? status;

  return (
    <Badge
      {...props}
      variant="outline"
      data-status={status ?? undefined}
      className={cn(
        toneClassName[resolvedTone],
        sizeClassName[size],
        "font-medium",
        className
      )}
    >
      {Icon ? (
        <Icon
          aria-hidden
          className={cn(
            "shrink-0",
            loading && "motion-safe:animate-spin motion-reduce:opacity-60"
          )}
        />
      ) : null}
      {label}
    </Badge>
  );
}
