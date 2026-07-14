import { Input as InputPrimitive, type InputProps } from "@base-ui/react/input";
import { cva, type VariantProps } from "class-variance-authority";
import type * as React from "react";

import { cn } from "@/shared/lib/utils";

const inputVariants = cva(
  "box-border rounded-lg border border-border bg-card px-3.5 py-0 text-sm leading-5 text-foreground shadow-none transition-[background-color,border-color,box-shadow,color] hover:border-border/80 file:text-sm file:font-medium focus-visible:border-[1.5px] focus-visible:border-ring aria-invalid:border-destructive/70 aria-invalid:focus-visible:border-[1.5px] aria-invalid:focus-visible:border-destructive file:text-foreground placeholder:text-muted-foreground w-full min-w-0 outline-none file:inline-flex file:border-0 file:bg-transparent disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-45 disabled:hover:border-border",
  {
    variants: {
      size: {
        default: "h-12 file:h-8",
        lg: "h-14 file:h-10",
        xl: "h-14 file:h-10",
      },
    },
    defaultVariants: {
      size: "default",
    },
  }
);

type InputComponentProps = React.ComponentProps<"input"> &
  VariantProps<typeof inputVariants> & {
    /**
     * Base UI's controlled-value callback. Base UI's `Field.Control`
     * intercepts the native `onChange` to wire validation state, so any
     * userland `onChange` handler is silently dropped — controlled
     * forms MUST use `onValueChange` instead.
     */
    onValueChange?: InputProps["onValueChange"];
  };

function Input({ className, type, size, ...props }: InputComponentProps) {
  return (
    <InputPrimitive
      type={type}
      data-slot="input"
      className={cn(inputVariants({ size, className }))}
      {...props}
    />
  );
}

export { Input, inputVariants };
