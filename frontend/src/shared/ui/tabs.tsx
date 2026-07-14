"use client";

import { Tabs as TabsPrimitive } from "@base-ui/react/tabs";
import { cva, type VariantProps } from "class-variance-authority";
import type * as React from "react";

import { cn } from "@/shared/lib/utils";

function Tabs({ className, ...props }: TabsPrimitive.Root.Props) {
  return <TabsPrimitive.Root className={cn("w-full", className)} {...props} />;
}

const tabsListVariants = cva(
  "inline-flex min-h-11 min-w-max items-center justify-start gap-[3px] rounded-lg bg-card p-1 text-foreground/70 ring-1 ring-inset ring-foreground/10",
  {
    variants: {
      variant: {
        default: "",
        line: "",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

interface TabsListProps
  extends TabsPrimitive.List.Props,
    VariantProps<typeof tabsListVariants> {}

function TabsList({ className, variant, ...props }: TabsListProps) {
  return (
    <TabsPrimitive.List
      className={cn(tabsListVariants({ variant }), className)}
      {...props}
    />
  );
}

const tabsTriggerVariants = cva(
  "ring-sidebar-ring inline-flex h-11 items-center justify-center gap-2 whitespace-nowrap rounded-lg px-4 text-sm font-medium text-foreground/70 transition-[background-color,color,box-shadow] duration-200 ease-out cursor-pointer hover:bg-sidebar-accent hover:text-sidebar-foreground/85 active:bg-sidebar-accent active:text-sidebar-foreground/85 focus-visible:outline-none focus-visible:ring-2 disabled:cursor-not-allowed disabled:opacity-50 data-[disabled]:cursor-not-allowed data-[disabled]:opacity-50 aria-disabled:cursor-not-allowed aria-disabled:opacity-50 data-[active]:bg-sidebar-accent data-[active]:text-sidebar-foreground/85 data-[active]:font-semibold [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default: "",
        line: "",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

interface TabsTriggerProps
  extends TabsPrimitive.Tab.Props,
    VariantProps<typeof tabsTriggerVariants> {}

function TabsTrigger({ className, variant, ...props }: TabsTriggerProps) {
  return (
    <TabsPrimitive.Tab
      className={cn(tabsTriggerVariants({ variant }), className)}
      {...props}
    />
  );
}

function TabsContent({ className, ...props }: TabsPrimitive.Panel.Props) {
  return (
    <TabsPrimitive.Panel
      className={cn(
        "mt-2 ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        className
      )}
      {...props}
    />
  );
}

export { Tabs, TabsContent, TabsList, TabsTrigger };
