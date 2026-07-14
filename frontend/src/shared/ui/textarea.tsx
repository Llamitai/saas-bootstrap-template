import type * as React from "react";

import { cn } from "@/shared/lib/utils";

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "box-border rounded-lg border border-border bg-card px-3.5 py-2.5 text-sm leading-5 text-foreground shadow-none transition-[background-color,border-color,box-shadow,color] hover:border-border/80 focus-visible:border-[1.5px] focus-visible:border-ring aria-invalid:border-destructive/70 aria-invalid:focus-visible:border-[1.5px] aria-invalid:focus-visible:border-destructive placeholder:text-muted-foreground flex field-sizing-content min-h-24 w-full outline-none disabled:cursor-not-allowed disabled:opacity-45 disabled:hover:border-border",
        className
      )}
      {...props}
    />
  );
}

export { Textarea };
