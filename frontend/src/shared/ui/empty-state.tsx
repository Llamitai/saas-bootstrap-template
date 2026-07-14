import type { LucideIcon } from "lucide-react";
import { Plus } from "lucide-react";
import { cn } from "@/shared/lib/utils";
import { Button, type ButtonProps } from "@/shared/ui/button";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description: string;
  variant?: "framed" | "plain";
  actionLabel?: string;
  onAction?: () => void;
  actionIcon?: LucideIcon;
  actionVariant?: ButtonProps["variant"];
  secondaryActionLabel?: string;
  onSecondaryAction?: () => void;
  secondaryActionIcon?: LucideIcon;
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  variant = "framed",
  actionLabel,
  onAction,
  actionIcon: ActionIcon = Plus,
  actionVariant,
  secondaryActionLabel,
  onSecondaryAction,
  secondaryActionIcon: SecondaryActionIcon,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex h-full w-full flex-col items-center justify-center rounded-lg text-center",
        variant === "framed" && "border border-dashed p-8"
      )}
    >
      <div className="flex flex-col items-center gap-2">
        <div className="flex h-20 w-20 items-center justify-center rounded-lg bg-muted">
          <Icon className="h-10 w-10 text-muted-foreground" />
        </div>
        <h3 className="mt-4 text-lg font-semibold">{title}</h3>
        <p className="text-muted-foreground mb-4 text-sm max-w-sm">
          {description}
        </p>
        {(actionLabel && onAction) ||
        (secondaryActionLabel && onSecondaryAction) ? (
          <div className="flex flex-wrap items-center justify-center gap-2">
            {secondaryActionLabel && onSecondaryAction && (
              <Button
                variant="outline"
                onClick={onSecondaryAction}
                className="gap-2"
              >
                {SecondaryActionIcon && (
                  <SecondaryActionIcon className="h-4 w-4" />
                )}
                {secondaryActionLabel}
              </Button>
            )}
            {actionLabel && onAction && (
              <Button
                variant={actionVariant}
                onClick={onAction}
                className="gap-2"
              >
                <ActionIcon className="h-4 w-4" />
                {actionLabel}
              </Button>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}
