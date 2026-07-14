import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/shared/lib/utils";

const badgeVariants = cva(
  "h-7 gap-1.5 rounded-lg border border-transparent px-2.5 py-0.5 text-xs font-medium transition-all has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2 [&>svg]:size-3.5! inline-flex items-center justify-center w-fit whitespace-nowrap shrink-0 [&>svg]:pointer-events-none focus-visible:ring-ring focus-visible:ring-[2px] focus-visible:ring-offset-2 aria-invalid:ring-destructive/20 aria-invalid:border-destructive transition-colors overflow-hidden group/badge",
  {
    variants: {
      variant: {
        default: "bg-accent text-accent-foreground [a]:hover:bg-accent/80",
        secondary: "bg-muted text-muted-foreground [a]:hover:bg-muted/80",
        destructive:
          "bg-destructive/10 [a]:hover:bg-destructive/20 focus-visible:ring-destructive/20 dark:focus-visible:ring-destructive/40 text-destructive-deep dark:bg-destructive/20",
        success:
          "bg-success/10 [a]:hover:bg-success/20 focus-visible:ring-success/20 dark:focus-visible:ring-success/40 text-success-deep dark:bg-success/20",
        warning:
          "bg-warning/10 [a]:hover:bg-warning/20 focus-visible:ring-warning/20 dark:focus-visible:ring-warning/40 text-warning-deep dark:bg-warning/20",
        outline:
          "border-border bg-card text-foreground [a]:hover:bg-muted [a]:hover:text-foreground",
        ghost: "text-muted-foreground hover:bg-muted hover:text-foreground",
        link: "text-primary underline-offset-4 hover:underline",
        info: "bg-[var(--md3-info-soft)] text-[var(--md3-info)] [a]:hover:bg-[var(--md3-info-soft)]",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

function Badge({
  className,
  variant = "default",
  render,
  ...props
}: useRender.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return useRender({
    defaultTagName: "span",
    props: mergeProps<"span">(
      {
        className: cn(badgeVariants({ className, variant })),
      },
      props
    ),
    render,
    state: {
      slot: "badge",
      variant,
    },
  });
}

export { Badge, badgeVariants };
