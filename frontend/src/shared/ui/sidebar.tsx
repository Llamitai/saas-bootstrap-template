"use client";

import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";
import { useIsMobile } from "@/shared/lib/use-mobile";
import { cn } from "@/shared/lib/utils";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { LineIcon } from "@/shared/ui/line-icon";
import { Separator } from "@/shared/ui/separator";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/shared/ui/sheet";
import { Skeleton } from "@/shared/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/shared/ui/tooltip";

const SIDEBAR_COOKIE_NAME = "sidebar_state";
const SIDEBAR_COOKIE_MAX_AGE = 60 * 60 * 24 * 7;
const SIDEBAR_WIDTH = "22.5rem";
const SIDEBAR_WIDTH_MOBILE = "min(22.5rem, calc(100vw - 3.5rem))";
const SIDEBAR_WIDTH_ICON = "5rem";
const SIDEBAR_KEYBOARD_SHORTCUT = "b";
const SIDEBAR_NAV_ITEM_HEIGHT_CLASSES = {
  default: "h-11",
  sm: "h-9",
  lg: "h-13",
  icon: "group-data-[collapsible=icon]:h-10!",
} as const;
const SIDEBAR_NAV_ITEM_SIZE_CLASSES = {
  default: `${SIDEBAR_NAV_ITEM_HEIGHT_CLASSES.default} text-sm`,
  sm: `${SIDEBAR_NAV_ITEM_HEIGHT_CLASSES.sm} text-xs`,
  lg: `${SIDEBAR_NAV_ITEM_HEIGHT_CLASSES.lg} text-sm group-data-[collapsible=icon]:p-0!`,
} as const;
const SIDEBAR_NAV_SUB_ITEM_SIZE_CLASSES = {
  md: SIDEBAR_NAV_ITEM_SIZE_CLASSES.default,
  sm: `${SIDEBAR_NAV_ITEM_SIZE_CLASSES.sm} px-4`,
} as const;
const SIDEBAR_NAV_ITEM_STATE_CLASSES =
  "hover:bg-sidebar-accent hover:text-sidebar-foreground/85 active:bg-sidebar-accent active:text-sidebar-foreground/85 data-active:bg-sidebar-accent data-active:text-sidebar-foreground/85 data-active:hover:bg-sidebar-accent data-active:hover:text-sidebar-foreground/85";

type SidebarContextProps = {
  state: "expanded" | "collapsed";
  open: boolean;
  setOpen: (open: boolean) => void;
  openMobile: boolean;
  setOpenMobile: (open: boolean) => void;
  isMobile: boolean;
  toggleSidebar: () => void;
};

const SidebarContext = React.createContext<SidebarContextProps | null>(null);

function useSidebar() {
  const context = React.useContext(SidebarContext);
  if (!context) {
    throw new Error("useSidebar must be used within a SidebarProvider.");
  }

  return context;
}

function SidebarProvider({
  defaultOpen = true,
  open: openProp,
  onOpenChange: setOpenProp,
  className,
  style,
  children,
  ...props
}: React.ComponentProps<"div"> & {
  defaultOpen?: boolean;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}) {
  const isMobile = useIsMobile();
  const [openMobile, setOpenMobile] = React.useState(false);

  // This is the internal state of the sidebar.
  // We use openProp and setOpenProp for control from outside the component.
  const [_open, _setOpen] = React.useState(defaultOpen);
  const open = openProp ?? _open;
  const setOpen = React.useCallback(
    (value: boolean | ((value: boolean) => boolean)) => {
      const openState = typeof value === "function" ? value(open) : value;
      if (setOpenProp) {
        setOpenProp(openState);
      } else {
        _setOpen(openState);
      }

      // This sets the cookie to keep the sidebar state.
      document.cookie = `${SIDEBAR_COOKIE_NAME}=${openState}; path=/; max-age=${SIDEBAR_COOKIE_MAX_AGE}`;
    },
    [setOpenProp, open]
  );

  // Helper to toggle the sidebar.
  const toggleSidebar = React.useCallback(() => {
    return isMobile ? setOpenMobile((open) => !open) : setOpen((open) => !open);
  }, [isMobile, setOpen]);

  // Adds a keyboard shortcut to toggle the sidebar.
  React.useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (
        event.key === SIDEBAR_KEYBOARD_SHORTCUT &&
        (event.metaKey || event.ctrlKey)
      ) {
        event.preventDefault();
        toggleSidebar();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [toggleSidebar]);

  // We add a state so that we can do data-state="expanded" or "collapsed".
  // This makes it easier to style the sidebar with Tailwind classes.
  const state = open ? "expanded" : "collapsed";

  const contextValue = React.useMemo<SidebarContextProps>(
    () => ({
      state,
      open,
      setOpen,
      isMobile,
      openMobile,
      setOpenMobile,
      toggleSidebar,
    }),
    [state, open, setOpen, isMobile, openMobile, toggleSidebar]
  );

  return (
    <SidebarContext.Provider value={contextValue}>
      <div
        data-slot="sidebar-wrapper"
        style={
          {
            "--sidebar-width": SIDEBAR_WIDTH,
            "--sidebar-width-icon": SIDEBAR_WIDTH_ICON,
            ...style,
          } as React.CSSProperties
        }
        className={cn(
          "group/sidebar-wrapper bg-md3-shell-background flex min-h-svh w-full",
          className
        )}
        {...props}
      >
        {children}
      </div>
    </SidebarContext.Provider>
  );
}

function Sidebar({
  side = "left",
  variant = "sidebar",
  collapsible = "offExamples",
  className,
  children,
  ...props
}: React.ComponentProps<"div"> & {
  side?: "left" | "right";
  variant?: "sidebar" | "floating" | "inset";
  collapsible?: "offExamples" | "icon" | "none";
}) {
  const { isMobile, state, openMobile, setOpenMobile } = useSidebar();

  if (collapsible === "none") {
    return (
      <div
        data-slot="sidebar"
        className={cn(
          "bg-sidebar text-sidebar-foreground flex h-full w-(--sidebar-width) flex-col",
          className
        )}
        {...props}
      >
        {children}
      </div>
    );
  }

  if (isMobile) {
    return (
      <Sheet open={openMobile} onOpenChange={setOpenMobile} {...props}>
        <SheetContent
          data-sidebar="sidebar"
          data-slot="sidebar"
          data-mobile="true"
          className="bg-sidebar text-sidebar-foreground max-w-none p-0 ring-0 data-[side=left]:w-(--sidebar-width) data-[side=left]:rounded-r-lg data-[side=right]:w-(--sidebar-width) data-[side=right]:rounded-l-lg [&>button]:hidden"
          style={
            {
              "--sidebar-width": SIDEBAR_WIDTH_MOBILE,
            } as React.CSSProperties
          }
          side={side}
        >
          <SheetHeader className="sr-only">
            <SheetTitle>Sidebar</SheetTitle>
            <SheetDescription>Displays the mobile sidebar.</SheetDescription>
          </SheetHeader>
          <div className="flex h-full w-full flex-col">{children}</div>
        </SheetContent>
      </Sheet>
    );
  }

  return (
    <div
      className="group peer text-sidebar-foreground hidden md:block"
      data-state={state}
      data-collapsible={state === "collapsed" ? collapsible : ""}
      data-variant={variant}
      data-side={side}
      data-slot="sidebar"
    >
      {/* This is what handles the sidebar gap on desktop */}
      <div
        data-slot="sidebar-gap"
        className={cn(
          "transition-[width] duration-300 ease-emphasized relative w-(--sidebar-width) bg-transparent",
          "group-data-[collapsible=offExamples]:w-0",
          "group-data-[side=right]:rotate-180",
          variant === "floating" || variant === "inset"
            ? "group-data-[collapsible=icon]:w-[calc(var(--sidebar-width-icon)+(--spacing(4)))]"
            : "group-data-[collapsible=icon]:w-(--sidebar-width-icon)"
        )}
      />
      <div
        data-slot="sidebar-container"
        className={cn(
          "fixed inset-y-0 z-20 hidden h-svh w-(--sidebar-width) transition-[left,right,width] duration-300 ease-emphasized md:flex",
          side === "left"
            ? "left-0 group-data-[collapsible=offExamples]:left-[calc(var(--sidebar-width)*-1)]"
            : "right-0 group-data-[collapsible=offExamples]:right-[calc(var(--sidebar-width)*-1)]",
          // Adjust the padding for floating and inset variants.
          variant === "floating" || variant === "inset"
            ? "p-2 group-data-[collapsible=icon]:w-[calc(var(--sidebar-width-icon)+(--spacing(4))+2px)]"
            : "p-0 group-data-[collapsible=icon]:w-(--sidebar-width-icon)",
          className
        )}
        {...props}
      >
        <div
          data-sidebar="sidebar"
          data-slot="sidebar-inner"
          className="bg-sidebar flex size-full flex-col overflow-hidden rounded-r-lg shadow-none group-data-[side=right]:rounded-r-none group-data-[side=right]:rounded-l-lg group-data-[collapsible=icon]:rounded-none"
        >
          {children}
        </div>
      </div>
    </div>
  );
}

function SidebarTrigger({
  className,
  onClick,
  ...props
}: React.ComponentProps<typeof Button>) {
  const { isMobile, openMobile, toggleSidebar, state } = useSidebar();

  return (
    <Button
      data-sidebar="trigger"
      data-slot="sidebar-trigger"
      data-state={state}
      aria-expanded={isMobile ? openMobile : state === "expanded"}
      variant="ghost"
      size="icon-sm"
      className={cn(
        "[&_svg]:transition-transform data-[state=collapsed]:[&_svg]:rotate-180",
        className
      )}
      onClick={(event) => {
        onClick?.(event);
        toggleSidebar();
      }}
      {...props}
    >
      <LineIcon name="menu" />
      <span className="sr-only">Toggle Sidebar</span>
    </Button>
  );
}

function SidebarRail({ className, ...props }: React.ComponentProps<"button">) {
  const { toggleSidebar } = useSidebar();

  return (
    <button
      data-sidebar="rail"
      data-slot="sidebar-rail"
      aria-label="Toggle Sidebar"
      tabIndex={-1}
      onClick={toggleSidebar}
      title="Toggle Sidebar"
      className={cn(
        "hover:after:bg-sidebar-border absolute inset-y-0 z-30 hidden w-4 -translate-x-1/2 transition-all duration-200 ease-out group-data-[side=left]:-right-4 group-data-[side=right]:left-0 after:absolute after:inset-y-4 after:left-1/2 after:w-[3px] after:rounded-lg after:bg-transparent sm:flex",
        "in-data-[side=left]:cursor-w-resize in-data-[side=right]:cursor-e-resize",
        "[[data-side=left][data-state=collapsed]_&]:cursor-e-resize [[data-side=right][data-state=collapsed]_&]:cursor-w-resize",
        "hover:group-data-[collapsible=offExamples]:bg-sidebar group-data-[collapsible=offExamples]:translate-x-0 group-data-[collapsible=offExamples]:after:left-full",
        "[[data-side=left][data-collapsible=offExamples]_&]:-right-2",
        "[[data-side=right][data-collapsible=offExamples]_&]:-left-2",
        className
      )}
      {...props}
    />
  );
}

function SidebarInset({ className, ...props }: React.ComponentProps<"main">) {
  return (
    <main
      data-slot="sidebar-inset"
      className={cn(
        // `min-w-0` es CLAVE: sin él, este flex item (`flex-1`) tiene
        // `min-width:auto` y no encoge por debajo del ancho de su contenido
        // (p. ej. tablas o paneles con ancho fijo), desbordando el
        // viewport y provocando scroll horizontal de página. Con `min-w-0` el main
        // respeta el ancho disponible y el contenido ancho hace su propio scroll
        // dentro de su contenedor `overflow-auto`.
        "bg-background md:peer-data-[variant=inset]:m-2 md:peer-data-[variant=inset]:ml-0 md:peer-data-[variant=inset]:rounded-lg md:peer-data-[variant=inset]:shadow-whisper md:peer-data-[variant=inset]:peer-data-[state=collapsed]:ml-2 relative flex w-full min-w-0 flex-1 flex-col",
        className
      )}
      {...props}
    />
  );
}

function SidebarInput({
  className,
  ...props
}: React.ComponentProps<typeof Input>) {
  return (
    <Input
      data-slot="sidebar-input"
      data-sidebar="input"
      className={cn("h-10 w-full bg-card shadow-none", className)}
      {...props}
    />
  );
}

function SidebarHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="sidebar-header"
      data-sidebar="header"
      className={cn(
        "gap-2 p-3 flex flex-col group-data-[collapsible=icon]:items-center group-data-[collapsible=icon]:px-0 group-data-[collapsible=icon]:py-3",
        className
      )}
      {...props}
    />
  );
}

function SidebarFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="sidebar-footer"
      data-sidebar="footer"
      className={cn(
        "gap-2 p-3 flex flex-col group-data-[collapsible=icon]:items-center group-data-[collapsible=icon]:px-0 group-data-[collapsible=icon]:py-3",
        className
      )}
      {...props}
    />
  );
}

function SidebarSeparator({
  className,
  ...props
}: React.ComponentProps<typeof Separator>) {
  return (
    <Separator
      data-slot="sidebar-separator"
      data-sidebar="separator"
      className={cn("bg-sidebar-border mx-7 w-auto", className)}
      {...props}
    />
  );
}

function SidebarContent({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="sidebar-content"
      data-sidebar="content"
      className={cn(
        "no-scrollbar gap-1 flex min-h-0 flex-1 flex-col overflow-auto group-data-[collapsible=icon]:items-center group-data-[collapsible=icon]:overflow-hidden",
        className
      )}
      {...props}
    />
  );
}

function SidebarGroup({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="sidebar-group"
      data-sidebar="group"
      className={cn(
        "px-3 py-1 relative flex w-full min-w-0 flex-col group-data-[collapsible=icon]:items-center group-data-[collapsible=icon]:px-0 group-data-[collapsible=icon]:py-0.5",
        className
      )}
      {...props}
    />
  );
}

function SidebarGroupLabel({
  className,
  render,
  ...props
}: useRender.ComponentProps<"div"> & React.ComponentProps<"div">) {
  return useRender({
    defaultTagName: "div",
    props: mergeProps<"div">(
      {
        className: cn(
          "text-sidebar-foreground/65 ring-sidebar-ring h-9 rounded-lg px-7 text-sm font-medium transition-[margin,opacity] duration-200 ease-out group-data-[collapsible=icon]:-mt-9 group-data-[collapsible=icon]:opacity-0 focus-visible:ring-2 [&>svg]:size-5 flex shrink-0 items-center outline-hidden [&>svg]:shrink-0",
          className
        ),
      },
      props
    ),
    render,
    state: {
      slot: "sidebar-group-label",
      sidebar: "group-label",
    },
  });
}

function SidebarGroupAction({
  className,
  render,
  ...props
}: useRender.ComponentProps<"button"> & React.ComponentProps<"button">) {
  return useRender({
    defaultTagName: "button",
    props: mergeProps<"button">(
      {
        className: cn(
          "text-sidebar-foreground ring-sidebar-ring hover:bg-sidebar-accent hover:text-sidebar-accent-foreground absolute top-3.5 right-3 w-5 rounded-lg p-0 focus-visible:ring-2 [&>svg]:size-4 flex aspect-square items-center justify-center outline-hidden transition-transform [&>svg]:shrink-0 after:absolute after:-inset-2 md:after:hidden group-data-[collapsible=icon]:hidden",
          className
        ),
      },
      props
    ),
    render,
    state: {
      slot: "sidebar-group-action",
      sidebar: "group-action",
    },
  });
}

function SidebarGroupContent({
  className,
  ...props
}: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="sidebar-group-content"
      data-sidebar="group-content"
      className={cn("text-sm w-full", className)}
      {...props}
    />
  );
}

function SidebarMenu({ className, ...props }: React.ComponentProps<"ul">) {
  return (
    <ul
      data-slot="sidebar-menu"
      data-sidebar="menu"
      className={cn(
        "gap-[3px] flex w-full min-w-0 flex-col group-data-[collapsible=icon]:items-center",
        className
      )}
      {...props}
    />
  );
}

function SidebarMenuItem({ className, ...props }: React.ComponentProps<"li">) {
  return (
    <li
      data-slot="sidebar-menu-item"
      data-sidebar="menu-item"
      className={cn(
        "group/menu-item relative group-data-[collapsible=icon]:flex group-data-[collapsible=icon]:justify-center",
        className
      )}
      {...props}
    />
  );
}

const sidebarMenuButtonVariants = cva(
  `ring-sidebar-ring ${SIDEBAR_NAV_ITEM_STATE_CLASSES} gap-3 rounded-lg px-7 text-left text-sm transition-[background-color,color,box-shadow,transform,width,height,padding] duration-200 ease-out group-has-data-[sidebar=menu-action]/menu-item:pr-10 ${SIDEBAR_NAV_ITEM_HEIGHT_CLASSES.icon} group-data-[collapsible=icon]:w-14! group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:gap-0 group-data-[collapsible=icon]:p-0! group-data-[collapsible=icon]:[&>span]:hidden focus-visible:ring-2 peer/menu-button flex w-full items-center overflow-hidden outline-hidden group/menu-button disabled:pointer-events-none disabled:opacity-50 aria-disabled:pointer-events-none aria-disabled:opacity-50 [&>span:last-child]:truncate data-active:[&_[data-sidebar-label]]:font-semibold [&_svg]:size-6 [&_svg]:shrink-0 data-active:[&_svg]:text-sidebar-foreground/85`,
  {
    variants: {
      variant: {
        default: "",
        outline:
          "bg-sidebar-foreground/8 shadow-[0_0_0_1px_var(--sidebar-border)]",
      },
      size: {
        default: SIDEBAR_NAV_ITEM_SIZE_CLASSES.default,
        sm: SIDEBAR_NAV_ITEM_SIZE_CLASSES.sm,
        lg: SIDEBAR_NAV_ITEM_SIZE_CLASSES.lg,
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

function SidebarMenuButton({
  render,
  isActive = false,
  variant = "default",
  size = "default",
  tooltip,
  className,
  ...props
}: useRender.ComponentProps<"button"> &
  React.ComponentProps<"button"> & {
    isActive?: boolean;
    tooltip?: string | React.ComponentProps<typeof TooltipContent>;
  } & VariantProps<typeof sidebarMenuButtonVariants>) {
  const { isMobile, state } = useSidebar();
  const button = useRender({
    defaultTagName: "button",
    props: mergeProps<"button">(
      {
        className: cn(sidebarMenuButtonVariants({ variant, size }), className),
      },
      props
    ),
    render,
    state: {
      slot: "sidebar-menu-button",
      sidebar: "menu-button",
      size,
      active: isActive,
    },
  });

  if (!tooltip) {
    return button;
  }

  // Make the rendered button (which may be a Link) the tooltip trigger by
  // passing it through as an element, so the caller's `render` is preserved.
  const tooltipContentProps =
    typeof tooltip === "string" ? { children: tooltip } : tooltip;

  return (
    <Tooltip>
      <TooltipTrigger render={button} />
      <TooltipContent
        side="right"
        align="center"
        hidden={state !== "collapsed" || isMobile}
        {...tooltipContentProps}
      />
    </Tooltip>
  );
}

function SidebarMenuAction({
  className,
  render,
  showOnHover = false,
  ...props
}: useRender.ComponentProps<"button"> &
  React.ComponentProps<"button"> & {
    showOnHover?: boolean;
  }) {
  return useRender({
    defaultTagName: "button",
    props: mergeProps<"button">(
      {
        className: cn(
          "text-sidebar-foreground ring-sidebar-ring hover:bg-sidebar-foreground/10 hover:text-sidebar-foreground peer-hover/menu-button:text-sidebar-foreground absolute right-7 aspect-square w-5 rounded-lg p-0 peer-data-[size=default]/menu-button:top-4 peer-data-[size=lg]/menu-button:top-4 peer-data-[size=sm]/menu-button:top-2 focus-visible:ring-2 [&>svg]:size-4 flex items-center justify-center outline-hidden transition-transform group-data-[collapsible=icon]:hidden after:absolute after:-inset-2 md:after:hidden [&>svg]:shrink-0",
          showOnHover &&
            "peer-data-active/menu-button:text-sidebar-accent-foreground group-focus-within/menu-item:opacity-100 group-hover/menu-item:opacity-100 data-open:opacity-100 md:opacity-0",
          className
        ),
      },
      props
    ),
    render,
    state: {
      slot: "sidebar-menu-action",
      sidebar: "menu-action",
    },
  });
}

function SidebarMenuBadge({
  className,
  ...props
}: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="sidebar-menu-badge"
      data-sidebar="menu-badge"
      className={cn(
        "text-sidebar-foreground peer-hover/menu-button:text-sidebar-foreground peer-data-active/menu-button:text-sidebar-accent-foreground pointer-events-none absolute right-7 flex h-5 min-w-5 rounded-lg px-1 text-xs font-medium peer-data-[size=default]/menu-button:top-4 peer-data-[size=lg]/menu-button:top-4 peer-data-[size=sm]/menu-button:top-2 flex items-center justify-center tabular-nums select-none group-data-[collapsible=icon]:hidden",
        className
      )}
      {...props}
    />
  );
}

function SidebarMenuSkeleton({
  className,
  showIcon = false,
  ...props
}: React.ComponentProps<"div"> & {
  showIcon?: boolean;
}) {
  // Random width between 50 to 90%.
  const [width, setWidth] = React.useState("70%");

  React.useEffect(() => {
    setWidth(`${Math.floor(Math.random() * 40) + 50}%`);
  }, []);

  return (
    <div
      data-slot="sidebar-menu-skeleton"
      data-sidebar="menu-skeleton"
      className={cn("h-8 gap-2 rounded-lg px-2 flex items-center", className)}
      {...props}
    >
      {showIcon && (
        <Skeleton
          className="size-4 rounded-lg"
          data-sidebar="menu-skeleton-icon"
        />
      )}
      <Skeleton
        className="h-4 max-w-(--skeleton-width) flex-1"
        data-sidebar="menu-skeleton-text"
        style={
          {
            "--skeleton-width": width,
          } as React.CSSProperties
        }
      />
    </div>
  );
}

function SidebarMenuSub({ className, ...props }: React.ComponentProps<"ul">) {
  return (
    <ul
      data-slot="sidebar-menu-sub"
      data-sidebar="menu-sub"
      className={cn(
        "mx-3 gap-[3px] px-2 py-1 group-data-[collapsible=icon]:hidden flex min-w-0 flex-col",
        className
      )}
      {...props}
    />
  );
}

function SidebarMenuSubItem({
  className,
  ...props
}: React.ComponentProps<"li">) {
  return (
    <li
      data-slot="sidebar-menu-sub-item"
      data-sidebar="menu-sub-item"
      className={cn("group/menu-sub-item relative", className)}
      {...props}
    />
  );
}

function SidebarMenuSubButton({
  render,
  size = "md",
  isActive = false,
  className,
  ...props
}: useRender.ComponentProps<"a"> &
  React.ComponentProps<"a"> & {
    size?: "sm" | "md";
    isActive?: boolean;
  }) {
  return useRender({
    defaultTagName: "a",
    props: mergeProps<"a">(
      {
        className: cn(
          `text-sidebar-foreground ring-sidebar-ring ${SIDEBAR_NAV_ITEM_STATE_CLASSES} [&>svg]:text-sidebar-foreground gap-3 rounded-lg px-5 focus-visible:ring-2 [&>svg]:size-5 flex min-w-0 items-center overflow-hidden outline-hidden group-data-[collapsible=icon]:hidden disabled:pointer-events-none disabled:opacity-50 aria-disabled:pointer-events-none aria-disabled:opacity-50 [&>span:last-child]:truncate data-active:[&_[data-sidebar-label]]:font-semibold [&>svg]:shrink-0 data-active:[&>svg]:text-sidebar-foreground/85`,
          SIDEBAR_NAV_SUB_ITEM_SIZE_CLASSES[size],
          className
        ),
      },
      props
    ),
    render,
    state: {
      slot: "sidebar-menu-sub-button",
      sidebar: "menu-sub-button",
      size,
      active: isActive,
    },
  });
}

export {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupAction,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInput,
  SidebarInset,
  SidebarMenu,
  SidebarMenuAction,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSkeleton,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarProvider,
  SidebarRail,
  SidebarSeparator,
  SidebarTrigger,
  useSidebar,
};
