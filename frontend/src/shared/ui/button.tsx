"use client";

import { Button as ButtonPrimitive } from "@base-ui/react/button";
import { cva, type VariantProps } from "class-variance-authority";
import type { ReactNode } from "react";

import { cn } from "@/shared/lib/utils";
import { LineIcon } from "@/shared/ui/line-icon";
import { Spinner } from "@/shared/ui/spinner";

const buttonVariants = cva(
  "group/button inline-flex shrink-0 cursor-pointer select-none items-center justify-center whitespace-nowrap rounded-lg border border-transparent bg-clip-padding text-[13px] font-semibold leading-5 tracking-normal outline-none transition-[background-color,border-color,color,box-shadow,opacity,transform] duration-150 focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:ring-offset-0 aria-invalid:ring-[2px] aria-invalid:ring-destructive/30 disabled:cursor-not-allowed disabled:opacity-50 aria-disabled:cursor-not-allowed aria-disabled:opacity-50 data-[loading=true]:cursor-wait data-[locked=true]:cursor-not-allowed [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-[18px]",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground shadow-raised hover:bg-primary/90 active:bg-primary/80",
        filled:
          "bg-primary text-primary-foreground shadow-raised hover:bg-primary/90 active:bg-primary/80",
        tonal:
          "bg-accent text-accent-foreground shadow-none hover:bg-accent/80 active:bg-accent/70",
        outline:
          "border-border/60 bg-card text-foreground shadow-none hover:border-border/80 hover:bg-muted/50 active:bg-muted/70 aria-expanded:border-border/80 aria-expanded:bg-muted/60 aria-expanded:text-foreground",
        outlined:
          "border-border/60 bg-card text-foreground shadow-none hover:border-border/80 hover:bg-muted/50 active:bg-muted/70 aria-expanded:border-border/80 aria-expanded:bg-muted/60 aria-expanded:text-foreground",
        secondary:
          "bg-accent text-accent-foreground shadow-none hover:bg-accent/80 active:bg-accent/70 aria-expanded:bg-accent aria-expanded:text-accent-foreground",
        ghost:
          "bg-transparent text-primary shadow-none hover:bg-accent hover:text-accent-foreground active:bg-accent/70 aria-expanded:bg-accent aria-expanded:text-accent-foreground",
        text: "bg-transparent text-primary shadow-none hover:bg-accent hover:text-accent-foreground active:bg-accent/70 aria-expanded:bg-accent aria-expanded:text-accent-foreground",
        destructive:
          "bg-destructive/10 text-destructive-deep shadow-none hover:bg-destructive/20 focus-visible:ring-destructive dark:bg-destructive/20 dark:hover:bg-destructive/30",
        success:
          "bg-success text-success-foreground shadow-raised hover:bg-success/90 focus-visible:ring-success",
        upload:
          "border-[#2e2e2e] bg-[#2e2e2e] text-white shadow-raised hover:border-[#2e2e2e] hover:bg-[#2e2e2e]/90 active:bg-[#2e2e2e]/80",
        link: "bg-transparent px-0 text-primary shadow-none underline-offset-4 hover:underline",
        fab: "bg-primary text-primary-foreground shadow-raised hover:bg-primary/90 active:bg-primary/80",
      },
      size: {
        default:
          "h-11 gap-2 px-4 in-data-[slot=button-group]:rounded-lg has-data-[icon=inline-end]:pr-3.5 has-data-[icon=inline-start]:pl-3.5",
        xs: "h-8 gap-1.5 px-3 text-xs in-data-[slot=button-group]:rounded-lg has-data-[icon=inline-end]:pr-2.5 has-data-[icon=inline-start]:pl-2.5 [&_svg:not([class*='size-'])]:size-3.5",
        sm: "h-10 gap-1.5 px-4 in-data-[slot=button-group]:rounded-lg has-data-[icon=inline-end]:pr-3 has-data-[icon=inline-start]:pl-3",
        lg: "h-12 gap-2 px-6 has-data-[icon=inline-end]:pr-5 has-data-[icon=inline-start]:pl-5",
        xl: "h-14 gap-2 px-7 has-data-[icon=inline-end]:pr-6 has-data-[icon=inline-start]:pl-6",
        // MD3 Expressive size-emphasis: reserve for the one primary decision/commit per region.
        hero: "h-14 gap-2.5 px-8 text-sm has-data-[icon=inline-end]:pr-7 has-data-[icon=inline-start]:pl-7 [&_svg:not([class*='size-'])]:size-5",
        icon: "size-11 p-0",
        "icon-xs":
          "size-8 p-0 in-data-[slot=button-group]:rounded-lg [&_svg:not([class*='size-'])]:size-3.5",
        "icon-sm": "size-10 p-0 in-data-[slot=button-group]:rounded-lg",
        "icon-lg": "size-12 p-0",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

type ButtonSize = NonNullable<VariantProps<typeof buttonVariants>["size"]>;

type ButtonProps = ButtonPrimitive.Props &
  VariantProps<typeof buttonVariants> & {
    /** Leading icon for action buttons. Replaced by status glyphs while loading/locked. */
    icon?: ReactNode;
    /** Trailing icon, for disclosure or submit-forward actions. */
    trailingIcon?: ReactNode;
    /** Standard busy state. Disables the button and swaps the leading icon for a spinner. */
    loading?: boolean;
    /** Standard locked state. Disables the button and swaps the leading icon for a lock. */
    locked?: boolean;
    loadingLabel?: string;
    lockedLabel?: string;
  };

function getStatusSpinnerSize(size: ButtonSize | null | undefined) {
  if (
    size === "xs" ||
    size === "sm" ||
    (typeof size === "string" && size.startsWith("icon"))
  ) {
    return "xs";
  }

  return "sm";
}

function Button({
  className,
  variant = "default",
  size = "default",
  icon,
  trailingIcon,
  loading = false,
  locked = false,
  loadingLabel = "Loading",
  lockedLabel = "Locked",
  disabled,
  children,
  ...props
}: ButtonProps) {
  const statusIcon = loading ? (
    <Spinner
      size={getStatusSpinnerSize(size)}
      className="border-current/30 border-t-current"
    />
  ) : locked ? (
    <LineIcon name="permissions" />
  ) : (
    icon
  );
  const isDisabled = Boolean(disabled || loading || locked);

  return (
    <ButtonPrimitive
      data-slot="button"
      data-loading={loading || undefined}
      data-locked={locked || undefined}
      aria-busy={loading || undefined}
      aria-disabled={locked || undefined}
      disabled={isDisabled}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    >
      {statusIcon ? <span data-icon="inline-start">{statusIcon}</span> : null}
      {children}
      {trailingIcon ? <span data-icon="inline-end">{trailingIcon}</span> : null}
      {loading ? <span className="sr-only">{loadingLabel}</span> : null}
      {locked ? <span className="sr-only">{lockedLabel}</span> : null}
    </ButtonPrimitive>
  );
}

export type { ButtonProps };
export { Button, buttonVariants };
