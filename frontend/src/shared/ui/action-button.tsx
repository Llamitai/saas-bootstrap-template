"use client";

import { AlertCircle, ArrowRight, CheckCircle2 } from "lucide-react";
import type { ComponentProps } from "react";

import { Button } from "@/shared/ui/button";

type ButtonProps = ComponentProps<typeof Button>;

type ActionButtonProps = ButtonProps;

/**
 * Semantic alias for user-triggered commands.
 * Loading, locked, disabled, icon, and trailing-icon behavior live in Button
 * so every action has the same state contract.
 */
export function ActionButton({
  icon,
  trailingIcon,
  variant,
  loading,
  locked,
  ...props
}: ActionButtonProps) {
  const defaultIcon =
    !loading && !locked && variant === "success" ? (
      <CheckCircle2 />
    ) : !loading && !locked && variant === "destructive" ? (
      <AlertCircle />
    ) : undefined;
  const statusIcon = icon ?? defaultIcon;
  const statusTrailingIcon =
    trailingIcon ??
    (!statusIcon && !loading && !locked ? <ArrowRight /> : undefined);

  return (
    <Button
      icon={statusIcon}
      trailingIcon={statusTrailingIcon}
      variant={variant}
      loading={loading}
      locked={locked}
      {...props}
    />
  );
}
