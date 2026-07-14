"use client";

import { Switch as SwitchPrimitive } from "@base-ui/react/switch";
import * as React from "react";
import { cn } from "@/shared/lib/utils";

const Switch = React.forwardRef<
  React.ElementRef<typeof SwitchPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof SwitchPrimitive.Root>
>(({ className, ...props }, ref) => (
  <SwitchPrimitive.Root
    className={cn(
      "peer inline-flex h-8 w-13 shrink-0 cursor-pointer items-center rounded-full p-1 transition-colors",
      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
      "disabled:cursor-not-allowed disabled:opacity-45",
      "data-[checked]:bg-primary data-[unchecked]:bg-[var(--md3-muted-3)]",
      className
    )}
    {...props}
    ref={ref}
  >
    <SwitchPrimitive.Thumb
      className={cn(
        "pointer-events-none block h-6 w-6 rounded-full bg-card shadow-whisper ring-0 transition-transform",
        "data-[checked]:translate-x-5 data-[unchecked]:translate-x-0"
      )}
    />
  </SwitchPrimitive.Root>
));
Switch.displayName = SwitchPrimitive.Root.displayName;

export { Switch };
