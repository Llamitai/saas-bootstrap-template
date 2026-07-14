"use client";

import { ChevronLeft, CircleHelp } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { Fragment } from "react";
import { SuperuserActionsMenu } from "@/features/app-shell/ui/superuser-actions-menu";
import { ThemeSwitcher } from "@/features/app-shell/ui/theme-switcher";
import { cn } from "@/shared/lib/utils";
import {
  Breadcrumb,
  BreadcrumbEllipsis,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/shared/ui/breadcrumb";
import { Button } from "@/shared/ui/button";
import { LocaleSwitcher } from "@/shared/ui/components/locale-switcher";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/shared/ui/dropdown-menu";
import { SidebarTrigger } from "@/shared/ui/sidebar";

export interface ShellBreadcrumbItem {
  label: string;
  href?: string;
}

interface ShellHeaderProps {
  breadcrumbItems: ShellBreadcrumbItem[];
  onHelpClick: () => void;
}

const MAX_UNCOLLAPSED_DESKTOP_CRUMBS = 4;

function getBreadcrumbKey(item: ShellBreadcrumbItem, index: number) {
  return `${item.href ?? item.label}-${index}`;
}

function getClosestNavigableAncestor(items: ShellBreadcrumbItem[]) {
  return [...items.slice(0, -1)].reverse().find((item) => item.href);
}

function HeaderBreadcrumbSegment({
  item,
  isCurrent,
  className,
  contentClassName,
}: {
  item: ShellBreadcrumbItem;
  isCurrent: boolean;
  className?: string;
  contentClassName?: string;
}) {
  return (
    <BreadcrumbItem className={cn("min-w-0", className)}>
      {isCurrent ? (
        <BreadcrumbPage className={contentClassName}>
          {item.label}
        </BreadcrumbPage>
      ) : item.href ? (
        <BreadcrumbLink
          render={<Link href={item.href} />}
          className={contentClassName}
        >
          {item.label}
        </BreadcrumbLink>
      ) : (
        <span
          className={cn(
            "min-w-0 truncate text-muted-foreground",
            contentClassName
          )}
        >
          {item.label}
        </span>
      )}
    </BreadcrumbItem>
  );
}

function BreadcrumbOverflow({
  items,
  label,
}: {
  items: ShellBreadcrumbItem[];
  label: string;
}) {
  return (
    <BreadcrumbItem className="shrink-0">
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button
              variant="ghost"
              size="icon-xs"
              aria-label={label}
              className="-mx-1 size-8 text-muted-foreground hover:text-foreground"
            >
              <BreadcrumbEllipsis />
            </Button>
          }
        />
        <DropdownMenuContent align="start" className="w-64">
          {items.map((item, index) =>
            item.href ? (
              <DropdownMenuItem
                key={getBreadcrumbKey(item, index)}
                render={<Link href={item.href} />}
                className="min-w-0"
              >
                <span className="truncate">{item.label}</span>
              </DropdownMenuItem>
            ) : (
              <DropdownMenuItem
                key={getBreadcrumbKey(item, index)}
                disabled
                className="min-w-0"
              >
                <span className="truncate">{item.label}</span>
              </DropdownMenuItem>
            )
          )}
        </DropdownMenuContent>
      </DropdownMenu>
    </BreadcrumbItem>
  );
}

function DesktopHeaderBreadcrumbs({
  breadcrumbItems,
  label,
  overflowLabel,
}: {
  breadcrumbItems: ShellBreadcrumbItem[];
  label: string;
  overflowLabel: string;
}) {
  const shouldCollapse =
    breadcrumbItems.length > MAX_UNCOLLAPSED_DESKTOP_CRUMBS;
  const leadingItems = shouldCollapse ? breadcrumbItems.slice(0, 1) : [];
  const overflowItems = shouldCollapse ? breadcrumbItems.slice(1, -2) : [];
  const trailingItems = shouldCollapse
    ? breadcrumbItems.slice(-2)
    : breadcrumbItems;

  return (
    <Breadcrumb aria-label={label} className="min-w-0">
      <BreadcrumbList className="flex-nowrap text-sm">
        {leadingItems.map((item, index) => (
          <Fragment key={getBreadcrumbKey(item, index)}>
            <HeaderBreadcrumbSegment
              item={item}
              isCurrent={false}
              contentClassName="max-w-36 truncate lg:max-w-44"
            />
            <BreadcrumbSeparator />
          </Fragment>
        ))}

        {overflowItems.length > 0 ? (
          <>
            <BreadcrumbOverflow items={overflowItems} label={overflowLabel} />
            <BreadcrumbSeparator />
          </>
        ) : null}

        {trailingItems.map((item, index) => {
          const originalIndex = shouldCollapse
            ? breadcrumbItems.length - trailingItems.length + index
            : index;
          const isLast = originalIndex === breadcrumbItems.length - 1;

          return (
            <Fragment key={getBreadcrumbKey(item, originalIndex)}>
              <HeaderBreadcrumbSegment
                item={item}
                isCurrent={isLast}
                contentClassName={cn(
                  "truncate",
                  isLast
                    ? "max-w-[min(34vw,28rem)] font-semibold"
                    : "max-w-40 lg:max-w-56"
                )}
              />
              {!isLast ? <BreadcrumbSeparator /> : null}
            </Fragment>
          );
        })}
      </BreadcrumbList>
    </Breadcrumb>
  );
}

function MobileHeaderBreadcrumbs({
  breadcrumbItems,
  label,
}: {
  breadcrumbItems: ShellBreadcrumbItem[];
  label: string;
}) {
  const currentItem = breadcrumbItems.at(-1);
  const parentItem = getClosestNavigableAncestor(breadcrumbItems);

  if (!currentItem) {
    return null;
  }

  return (
    <Breadcrumb aria-label={label} className="min-w-0">
      <BreadcrumbList className="flex-nowrap">
        <BreadcrumbItem className="min-w-0 max-w-full">
          {parentItem?.href ? (
            <BreadcrumbLink
              render={<Link href={parentItem.href} />}
              className="h-11 max-w-full gap-1.5 px-1.5 font-medium text-foreground"
            >
              <ChevronLeft className="size-4 shrink-0" aria-hidden="true" />
              <span className="truncate">{parentItem.label}</span>
            </BreadcrumbLink>
          ) : (
            <BreadcrumbPage className="max-w-[52vw] font-semibold">
              {currentItem.label}
            </BreadcrumbPage>
          )}
        </BreadcrumbItem>
      </BreadcrumbList>
    </Breadcrumb>
  );
}

export function ShellHeader({
  breadcrumbItems,
  onHelpClick,
}: ShellHeaderProps) {
  const t = useTranslations("AppShell");

  return (
    <header className="sticky top-0 z-30 border-b border-border/70 bg-background/95 shadow-[0_1px_0_color-mix(in_oklch,var(--foreground)_4%,transparent)] backdrop-blur supports-[backdrop-filter]:bg-background/88">
      <div className="flex h-[72px] min-w-0 items-center gap-3 px-3 md:px-5">
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <SidebarTrigger className="size-11 shrink-0 text-foreground hover:bg-accent hover:text-accent-foreground" />
          <div className="hidden h-11 min-w-0 flex-1 items-center rounded-lg bg-input px-4 text-foreground ring-1 ring-border/70 lg:flex">
            <DesktopHeaderBreadcrumbs
              breadcrumbItems={breadcrumbItems}
              label={t("breadcrumbsLabel")}
              overflowLabel={t("breadcrumbsOverflow")}
            />
          </div>
          <div className="min-w-0 flex-1 lg:hidden">
            <MobileHeaderBreadcrumbs
              breadcrumbItems={breadcrumbItems}
              label={t("breadcrumbsLabel")}
            />
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-1.5">
          <Button
            variant="secondary"
            onClick={onHelpClick}
            className="hidden text-foreground hover:bg-accent hover:text-accent-foreground lg:inline-flex"
          >
            <CircleHelp className="size-5 sm:mr-1" />
            <span>{t("help")}</span>
          </Button>
          <Button
            variant="secondary"
            size="icon-lg"
            onClick={onHelpClick}
            className="text-foreground hover:bg-accent hover:text-accent-foreground lg:hidden"
            aria-label={t("help")}
          >
            <CircleHelp className="size-5" />
          </Button>
          <SuperuserActionsMenu />
          <LocaleSwitcher
            size="default"
            className="h-11! min-w-[4.75rem] rounded-lg border-0 border-b-0 bg-muted px-3 text-xs text-foreground hover:bg-accent hover:text-accent-foreground focus-visible:border-0 max-lg:hidden"
          />
          <ThemeSwitcher />
        </div>
      </div>
    </header>
  );
}
