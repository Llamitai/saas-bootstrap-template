"use client";

import Image from "next/image";
import { useCallback } from "react";
import type { Tenant } from "@/entities/tenant";
import { useSessionStore } from "@/features/auth";
import { useSelectTenantMutation, useTenantsQuery } from "@/features/tenants";
import { Badge } from "@/shared/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/shared/ui/dropdown-menu";
import { LineIcon } from "@/shared/ui/line-icon";
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/shared/ui/sidebar";

function TenantLogo({ tenant }: { tenant: Tenant }) {
  return (
    <div className="bg-sidebar-primary text-sidebar-primary-foreground ring-sidebar-border/70 flex aspect-square size-9 items-center justify-center overflow-hidden rounded-lg ring-1">
      {tenant.logoUrl ? (
        <Image
          src={tenant.logoUrl}
          alt={tenant.name}
          width={36}
          height={36}
          className="size-full object-cover"
          unoptimized
        />
      ) : (
        <LineIcon name="tenant" size={18} />
      )}
    </div>
  );
}

const tenantSwitcherButtonClass =
  "gap-2.5 bg-sidebar-foreground/[0.04] px-3 hover:bg-sidebar-accent";

function resolveTargetPath(pathname: string): string {
  return pathname;
}

export function TenantHead() {
  const tenant = useSessionStore((s) => s.tenant);
  const { data: tenants = [], isLoading: loading } = useTenantsQuery();
  const selectTenant = useSelectTenantMutation();
  const { isMobile } = useSidebar();

  const hasMultipleTenants = tenants.length > 1;

  const handleTenantChange = useCallback(
    (option: Tenant) => {
      if (option.uuid === tenant?.uuid) return;
      selectTenant.mutateAsync(option).then(() => {
        // Hard reload to nuke React Query caches, in-flight requests, and
        // zustand stores hydrated from the previous tenant. router.refresh()
        // alone re-runs Server Components but leaves client caches stale.
        // Read pathname on demand so this component doesn't subscribe to
        // every route change (rerender-defer-reads).
        if (typeof window === "undefined") return;
        window.location.assign(resolveTargetPath(window.location.pathname));
      });
    },
    [selectTenant, tenant?.uuid]
  );

  if (!tenant) return null;

  const subtitleParts = [tenant.countryCode].filter(Boolean);

  const summary = (
    <>
      <TenantLogo tenant={tenant} />
      <div className="grid flex-1 text-left text-sm leading-tight group-data-[collapsible=icon]:hidden">
        <span className="truncate font-semibold">{tenant.name}</span>
        <span className="truncate text-xs text-sidebar-foreground/70">
          {subtitleParts.join(" / ")}
        </span>
      </div>
      {hasMultipleTenants && (
        <LineIcon
          name="switchTenant"
          size={16}
          className="ml-auto group-data-[collapsible=icon]:hidden"
        />
      )}
    </>
  );

  if (!hasMultipleTenants) {
    return (
      <SidebarMenu>
        <SidebarMenuItem>
          <SidebarMenuButton size="lg" className={tenantSwitcherButtonClass}>
            {summary}
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    );
  }

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <SidebarMenuButton
            size="lg"
            className={`${tenantSwitcherButtonClass} cursor-pointer data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground`}
            render={(props) => (
              <DropdownMenuTrigger {...props}>{summary}</DropdownMenuTrigger>
            )}
          />
          <DropdownMenuContent
            className="w-(--radix-dropdown-menu-trigger-width) min-w-64 rounded-lg"
            align="start"
            side={isMobile ? "bottom" : "right"}
            sideOffset={4}
          >
            <DropdownMenuGroup>
              <DropdownMenuLabel className="text-muted-foreground text-xs">
                Cambiar Tenant
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              {loading ? (
                <DropdownMenuItem disabled>
                  Cargando tenants...
                </DropdownMenuItem>
              ) : (
                tenants.map((option) => (
                  <DropdownMenuItem
                    key={option.uuid}
                    onClick={() => handleTenantChange(option)}
                    className="flex cursor-pointer items-center gap-3 p-3"
                  >
                    <LineIcon
                      name="tenant"
                      size={16}
                      className="text-muted-foreground"
                    />
                    <div className="flex flex-1 flex-col gap-0.5">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium">{option.name}</span>
                        {tenant.uuid === option.uuid && (
                          <Badge variant="default" className="text-xs">
                            Actual
                          </Badge>
                        )}
                      </div>
                      <div className="text-muted-foreground flex items-center gap-1 text-xs">
                        <span>{option.countryCode || option.slug}</span>
                      </div>
                    </div>
                  </DropdownMenuItem>
                ))
              )}
            </DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
