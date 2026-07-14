"use client";

import { type ReactNode, useState } from "react";
import { AppSidebar } from "@/features/app-shell/ui/app-sidebar";
import { HelpSidebar } from "@/features/app-shell/ui/help-sidebar";
import { ShellHeader } from "@/features/app-shell/ui/shell-header";
import { SidebarInset, SidebarProvider } from "@/shared/ui/sidebar";

export interface BreadcrumbItemType {
  label: string;
  href?: string;
}

interface AppShellProps {
  children: ReactNode;
  breadcrumbItems: BreadcrumbItemType[];
  activePath?: string;
}

export function AppShell({
  children,
  breadcrumbItems,
  activePath,
}: AppShellProps) {
  const [helpSidebarOpen, setHelpSidebarOpen] = useState(false);

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
