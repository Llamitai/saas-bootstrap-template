"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { logout, useSession, useSessionActions } from "@/features/auth";
import { Avatar, AvatarFallback, AvatarImage } from "@/shared/ui/avatar";
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

function getUserInitials(
  firstName?: string | null,
  lastName?: string | null,
  username?: string
): string {
  if (firstName && lastName)
    return `${firstName[0]}${lastName[0]}`.toUpperCase();
  if (firstName) return firstName.slice(0, 2).toUpperCase();
  if (lastName) return lastName.slice(0, 2).toUpperCase();
  if (username) return username.slice(0, 2).toUpperCase();
  return "U";
}

function getDisplayName(
  firstName?: string | null,
  lastName?: string | null,
  username?: string
): string {
  if (firstName || lastName)
    return [firstName, lastName].filter(Boolean).join(" ");
  return username ?? "";
}

export function NavUser() {
  const t = useTranslations("NavUser");
  const { isMobile } = useSidebar();
  const router = useRouter();
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const { clearSession } = useSessionActions();
  const { user } = useSession();

  const displayName = getDisplayName(
    user?.firstName,
    user?.lastName,
    user?.username
  );
  const initials = getUserInitials(
    user?.firstName,
    user?.lastName,
    user?.username
  );
  const email = user?.emailAddress?.email ?? "";
  const avatar = user?.photoUrl ?? "";

  const handleLogout = async () => {
    setIsLoggingOut(true);

    try {
      await logout();
      clearSession();
      router.push("/");
    } catch {
      clearSession();
      router.push("/");
    } finally {
      setIsLoggingOut(false);
    }
  };

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <SidebarMenuButton
            size="lg"
            className="cursor-pointer gap-3 px-4! pr-3! data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground group-data-[collapsible=icon]:px-0!"
            render={(props) => (
              <DropdownMenuTrigger {...props}>
                <Avatar className="h-9 w-9 rounded-full">
                  <AvatarImage src={avatar} alt={displayName} />
                  <AvatarFallback className="rounded-full">
                    {initials}
                  </AvatarFallback>
                </Avatar>
                <div className="grid flex-1 text-left text-sm leading-tight group-data-[collapsible=icon]:hidden">
                  <span className="truncate font-semibold">{displayName}</span>
                  <span className="truncate text-xs text-sidebar-foreground/70">
                    {email}
                  </span>
                </div>
                <span className="ml-auto flex size-8 shrink-0 items-center justify-center rounded-lg text-sidebar-foreground/55 transition-colors group-data-[collapsible=icon]:hidden group-hover/menu-button:bg-sidebar-foreground/8 group-hover/menu-button:text-sidebar-foreground">
                  <LineIcon name="chevronRight" size={18} />
                </span>
              </DropdownMenuTrigger>
            )}
          />
          <DropdownMenuContent
            className="w-(--radix-dropdown-menu-trigger-width) min-w-56 rounded-lg"
            side={isMobile ? "bottom" : "right"}
            align="end"
            sideOffset={4}
          >
            <DropdownMenuGroup>
              <DropdownMenuLabel className="p-0 font-normal">
                <div className="flex items-center gap-2 px-1 py-1.5 text-left text-sm">
                  <Avatar className="h-9 w-9 rounded-full">
                    <AvatarImage src={avatar} alt={displayName} />
                    <AvatarFallback className="rounded-full">
                      {initials}
                    </AvatarFallback>
                  </Avatar>
                  <div className="grid flex-1 text-left text-sm leading-tight">
                    <span className="truncate font-semibold">
                      {displayName}
                    </span>
                    <span className="truncate text-xs text-muted-foreground">
                      {email}
                    </span>
                  </div>
                </div>
              </DropdownMenuLabel>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuGroup>
              <DropdownMenuItem
                className="cursor-pointer"
                onClick={() => router.push("/profile")}
              >
                <LineIcon name="profile" size={18} />
                {t("profile")}
              </DropdownMenuItem>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              className="cursor-pointer"
              onClick={handleLogout}
              disabled={isLoggingOut}
            >
              <LineIcon name="logout" size={18} />
              {isLoggingOut ? t("loggingOut") : t("logout")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
