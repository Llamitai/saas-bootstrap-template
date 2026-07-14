"use client";

import { cva, type VariantProps } from "class-variance-authority";
import type * as React from "react";

import { cn } from "@/shared/lib/utils";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { Textarea } from "@/shared/ui/textarea";

function InputGroup({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="input-group"
      role="group"
      className={cn(
        "h-[54px] rounded-lg border border-border bg-card shadow-none transition-[background-color,border-color,box-shadow,color] hover:border-border/80 focus-within:border-[1.5px] focus-within:border-ring focus-within:hover:border-ring has-[[data-slot][aria-invalid=true]]:border-destructive/70 has-[[data-slot][aria-invalid=true]]:focus-within:border-[1.5px] has-[[data-slot][aria-invalid=true]]:focus-within:border-destructive has-[[data-slot][aria-invalid=true]]:focus-within:hover:border-destructive has-[>[data-align=block-end]]:h-auto has-[>[data-align=block-end]]:flex-col has-[>[data-align=block-start]]:h-auto has-[>[data-align=block-start]]:flex-col has-[>[data-align=block-end]]:[&>input]:pt-3 has-[>[data-align=block-start]]:[&>input]:pb-3 has-[>[data-align=inline-end]]:[&>input]:pr-1.5 has-[>[data-align=inline-start]]:[&>input]:pl-1.5 [[data-slot=combobox-content]_&]:h-[54px] group/input-group relative flex w-full min-w-0 items-center outline-none has-[>textarea]:h-auto",
        className
      )}
      {...props}
    />
  );
}

const inputGroupAddonVariants = cva(
  "text-muted-foreground h-auto gap-2 py-1.5 text-base font-medium group-data-[disabled=true]/input-group:opacity-50 [&>kbd]:rounded-sm [&>svg:not([class*='size-'])]:size-5 flex cursor-text items-center justify-center select-none",
  {
    variants: {
      align: {
        "inline-start":
          "pl-2 has-[>button]:ml-[-0.25rem] has-[>kbd]:ml-[-0.15rem] order-first",
        "inline-end":
          "pr-2 has-[>button]:mr-[-0.25rem] has-[>kbd]:mr-[-0.15rem] order-last",
        "block-start":
          "px-2.5 pt-2 group-has-[>input]/input-group:pt-2 [.border-b]:pb-2 order-first w-full justify-start",
        "block-end":
          "px-2.5 pb-2 group-has-[>input]/input-group:pb-2 [.border-t]:pt-2 order-last w-full justify-start",
      },
    },
    defaultVariants: {
      align: "inline-start",
    },
  }
);

function InputGroupAddon({
  className,
  align = "inline-start",
  ...props
}: React.ComponentProps<"div"> & VariantProps<typeof inputGroupAddonVariants>) {
  return (
    <div
      role="group"
      data-slot="input-group-addon"
      data-align={align}
      className={cn(inputGroupAddonVariants({ align }), className)}
      onClick={(e) => {
        if ((e.target as HTMLElement).closest("button")) {
          return;
        }
        e.currentTarget.parentElement?.querySelector("input")?.focus();
      }}
      {...props}
    />
  );
}

const inputGroupButtonVariants = cva(
  "gap-2 text-sm shadow-none flex items-center",
  {
    variants: {
      size: {
        xs: "h-8 gap-1 rounded-lg px-2 [&>svg:not([class*='size-'])]:size-3.5",
        sm: "",
        "icon-xs": "size-8 rounded-lg p-0 has-[>svg]:p-0",
        "icon-sm": "size-8 p-0 has-[>svg]:p-0",
      },
    },
    defaultVariants: {
      size: "xs",
    },
  }
);

function InputGroupButton({
  className,
  type = "button",
  variant = "ghost",
  size = "xs",
  ...props
}: Omit<React.ComponentProps<typeof Button>, "size" | "type"> &
  VariantProps<typeof inputGroupButtonVariants> & {
    type?: "button" | "submit" | "reset";
  }) {
  return (
    <Button
      type={type}
      data-size={size}
      variant={variant}
      className={cn(inputGroupButtonVariants({ size }), className)}
      {...props}
    />
  );
}

function InputGroupText({ className, ...props }: React.ComponentProps<"span">) {
  return (
    <span
      className={cn(
        "text-muted-foreground gap-2 text-sm [&_svg:not([class*='size-'])]:size-4 flex items-center [&_svg]:pointer-events-none",
        className
      )}
      {...props}
    />
  );
}

function InputGroupInput({
  className,
  size: _size,
  ...props
}: React.ComponentProps<"input">) {
  return (
    <Input
      data-slot="input-group-control"
      className={cn(
        "h-full rounded-none border-0 bg-transparent shadow-none ring-0 focus-visible:ring-0 aria-invalid:ring-0 flex-1",
        className
      )}
      {...props}
    />
  );
}

function InputGroupTextarea({
  className,
  ...props
}: React.ComponentProps<"textarea">) {
  return (
    <Textarea
      data-slot="input-group-control"
      className={cn(
        "rounded-none border-0 bg-transparent py-2 shadow-none ring-0 hover:bg-transparent focus-visible:ring-0 aria-invalid:ring-0 dark:bg-transparent flex-1 resize-none",
        className
      )}
      {...props}
    />
  );
}

export {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
  InputGroupText,
  InputGroupTextarea,
};
