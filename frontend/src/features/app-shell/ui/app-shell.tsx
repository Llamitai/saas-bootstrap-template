"use client";

import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { type ReactNode, useState } from "react";
import { AppSidebar } from "@/features/app-shell/ui/app-sidebar";
import { HelpSidebar } from "@/features/app-shell/ui/help-sidebar";
import { ShellHeader } from "@/features/app-shell/ui/shell-header";
import { resolveShellRoute } from "@/features/app-shell/ui/sidebar-config";
import { SidebarInset, SidebarProvider } from "@/shared/ui/sidebar";

export interface BreadcrumbItemType {
  label: string;
  href?: string;
}

interface AppShellProps {
  children: ReactNode;
}

/**
 * Authenticated shell, mounted once by the (shell) route-group layout. The
 * active nav entry and the breadcrumb derive from the current pathname.
 */
export function AppShell({ children }: AppShellProps) {
  const [helpSidebarOpen, setHelpSidebarOpen] = useState(false);
  const pathname = usePathname();
  const tNav = useTranslations("Nav");
  const tNavUser = useTranslations("NavUser");
  const route = resolveShellRoute(pathname);
  const activePath = route?.activePath;
  const breadcrumbItems: BreadcrumbItemType[] = route
    ? [
        {
          label:
            route.label.namespace === "Nav"
              ? tNav(route.label.key)
              : tNavUser(route.label.key),
        },
      ]
    : [];

  return (
    <SidebarProvider>
      <AppSidebar activePath={activePath} />
      <SidebarInset className="h-svh">
        <ShellHeader
          breadcrumbItems={breadcrumbItems}
          onHelpClick={() => setHelpSidebarOpen(true)}
        />
        <div className="flex min-h-0 flex-1 flex-col gap-4 p-4 md:p-6">
          <div className="flex min-h-0 w-full flex-1 flex-col">{children}</div>
        </div>
      </SidebarInset>
      <HelpSidebar open={helpSidebarOpen} onOpenChange={setHelpSidebarOpen} />
    </SidebarProvider>
  );
}
