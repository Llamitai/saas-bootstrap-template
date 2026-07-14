"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { NavActiveIndicator } from "@/features/app-shell/ui/nav-active-indicator";
import { LineIcon, type LineIconName } from "@/shared/ui/line-icon";
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/shared/ui/sidebar";

export function NavProjects({
  projects,
  activePath,
}: {
  projects: {
    i18nKey: string;
    url: string;
    icon: LineIconName;
    disabled?: boolean;
  }[];
  activePath?: string;
}) {
  const t = useTranslations("Nav");

  return (
    <SidebarGroup className="group-data-[collapsible=icon]:hidden">
      <SidebarGroupLabel>{t("team")}</SidebarGroupLabel>
      <SidebarMenu>
        {projects.map((item) => {
          const label = t(item.i18nKey);
          const isItemActive = activePath === item.url;
          return (
            <SidebarMenuItem key={item.i18nKey}>
              {item.disabled ? (
                <SidebarMenuButton
                  disabled
                  className="opacity-50 cursor-not-allowed"
                >
                  <LineIcon name={item.icon} />
                  <span data-sidebar-label>{label}</span>
                </SidebarMenuButton>
              ) : (
                <>
                  {isItemActive && <NavActiveIndicator />}
                  <SidebarMenuButton
                    isActive={isItemActive}
                    render={(props) => (
                      <Link href={item.url} {...props}>
                        <LineIcon name={item.icon} />
                        <span data-sidebar-label>{label}</span>
                      </Link>
                    )}
                  />
                </>
              )}
            </SidebarMenuItem>
          );
        })}
      </SidebarMenu>
    </SidebarGroup>
  );
}
