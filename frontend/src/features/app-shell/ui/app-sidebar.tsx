"use client";

import { LayoutGroup } from "motion/react";
import type * as React from "react";
import { NavMain } from "@/features/app-shell/ui/nav-main";
import { NavProjects } from "@/features/app-shell/ui/nav-projects";
import { NavUser } from "@/features/app-shell/ui/nav-user";
import { sidebarConfig } from "@/features/app-shell/ui/sidebar-config";
import { TenantHead } from "@/features/app-shell/ui/tenant-head";
import { usePermissions } from "@/features/auth";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
} from "@/shared/ui/sidebar";

export function AppSidebar({
  activePath,
  ...props
}: React.ComponentProps<typeof Sidebar> & { activePath?: string }) {
  const { hasPermission } = usePermissions();

  const navMainItems = sidebarConfig.navMain.map((item) => ({
    ...item,
    disabled:
      item.disabled ||
      (item.requiredPermission
        ? !hasPermission(item.requiredPermission)
        : false),
  }));

  const projectItems = sidebarConfig.projects.map((item) => ({
    ...item,
    disabled:
      item.disabled ||
      (item.requiredPermission
        ? !hasPermission(item.requiredPermission)
        : false),
  }));

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader>
        <div className="min-w-0 group-data-[collapsible=icon]:flex-none">
          <TenantHead />
        </div>
      </SidebarHeader>
      <SidebarContent>
        <LayoutGroup id="app-nav">
          <NavMain items={navMainItems} activePath={activePath} />
          <NavProjects projects={projectItems} activePath={activePath} />
        </LayoutGroup>
      </SidebarContent>
      <SidebarFooter>
        <NavUser />
      </SidebarFooter>
    </Sidebar>
  );
}
