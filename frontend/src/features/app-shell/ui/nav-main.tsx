"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { NavActiveIndicator } from "@/features/app-shell/ui/nav-active-indicator";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/shared/ui/collapsible";
import { LineIcon, type LineIconName } from "@/shared/ui/line-icon";
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
} from "@/shared/ui/sidebar";

export function NavMain({
  items,
  activePath,
}: {
  items: {
    i18nKey: string;
    url: string;
    icon?: LineIconName;
    isActive?: boolean;
    disabled?: boolean;
    items?: {
      i18nKey: string;
      url: string;
    }[];
  }[];
  activePath?: string;
}) {
  const t = useTranslations("Nav");

  return (
    <SidebarGroup>
      <SidebarGroupLabel>{t("platform")}</SidebarGroupLabel>
      <SidebarMenu>
        {items.map((item) => {
          const isItemActive =
            activePath === item.url ||
            item.items?.some((subItem) => subItem.url === activePath);
          const isActive = item.isActive || isItemActive;
          const label = t(item.i18nKey);

          if (!item.items || item.items.length === 0) {
            return (
              <SidebarMenuItem key={item.i18nKey}>
                {item.disabled ? (
                  <SidebarMenuButton
                    disabled
                    aria-label={label}
                    tooltip={label}
                    className="opacity-50 cursor-not-allowed"
                  >
                    {item.icon && <LineIcon name={item.icon} />}
                    <span data-sidebar-label>{label}</span>
                  </SidebarMenuButton>
                ) : (
                  <>
                    {isItemActive && <NavActiveIndicator />}
                    <SidebarMenuButton
                      isActive={isItemActive}
                      tooltip={label}
                      render={(props) => (
                        <Link href={item.url} aria-label={label} {...props}>
                          {item.icon && <LineIcon name={item.icon} />}
                          <span data-sidebar-label>{label}</span>
                        </Link>
                      )}
                    />
                  </>
                )}
              </SidebarMenuItem>
            );
          }

          return (
            <SidebarMenuItem key={item.i18nKey}>
              <Collapsible defaultOpen={isActive} className="group/collapsible">
                <CollapsibleTrigger
                  render={(props) => (
                    <SidebarMenuButton {...props} isActive={isItemActive}>
                      {item.icon && <LineIcon name={item.icon} />}
                      <span data-sidebar-label>{label}</span>
                      <LineIcon
                        name="chevronRight"
                        size={20}
                        className="text-sidebar-foreground/50 ml-auto transition-transform duration-200 group-data-[collapsible=icon]:hidden group-data-[open]/collapsible:rotate-90"
                      />
                    </SidebarMenuButton>
                  )}
                />
                <CollapsibleContent>
                  <SidebarMenuSub>
                    {item.items.map((subItem) => (
                      <SidebarMenuSubItem key={subItem.i18nKey}>
                        <SidebarMenuSubButton
                          isActive={activePath === subItem.url}
                          render={(props) => (
                            <Link href={subItem.url} {...props}>
                              <span data-sidebar-label>
                                {t(subItem.i18nKey)}
                              </span>
                            </Link>
                          )}
                        />
                      </SidebarMenuSubItem>
                    ))}
                  </SidebarMenuSub>
                </CollapsibleContent>
              </Collapsible>
            </SidebarMenuItem>
          );
        })}
      </SidebarMenu>
    </SidebarGroup>
  );
}
