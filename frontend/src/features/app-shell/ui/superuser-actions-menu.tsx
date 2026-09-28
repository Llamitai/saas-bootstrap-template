"use client";

import { Crown } from "lucide-react";
import { useTranslations } from "next-intl";
import { useSessionStore } from "@/features/auth";
import {
  OnboardTenantWizard,
  useOnboardTenantWizardStore,
} from "@/features/superuser";
import { detectBrowserTimezone } from "@/shared/catalogs/timezones";
import { Button } from "@/shared/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/shared/ui/dropdown-menu";

/**
 * Header-level dropdown that exposes superuser-only actions. Renders
 * nothing when the current session user is not a superuser. New
 * actions plug into the menu by adding more `DropdownMenuItem`s below
 * the first entry.
 */
export function SuperuserActionsMenu() {
  const t = useTranslations("AppShell");
  const isSuperuser = useSessionStore((s) => s.user?.isSuperuser === true);
  const openOnboardWizard = useOnboardTenantWizardStore((s) => s.openWizard);

  if (!isSuperuser) return null;

  const handleRegisterTenant = () => {
    openOnboardWizard({
      countryCode: "MX",
      currencyCode: "MXN",
      timeZone: detectBrowserTimezone(),
    });
  };

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button
              variant="secondary"
              size="icon"
              aria-label={t("superuserActions")}
            >
              <Crown className="h-[1.2rem] w-[1.2rem] text-warning-deep" />
            </Button>
          }
        />
        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuGroup>
            <DropdownMenuLabel className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">
              {t("superuser")}
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleRegisterTenant}>
              {t("registerTenant")}
            </DropdownMenuItem>
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
      <OnboardTenantWizard />
    </>
  );
}
