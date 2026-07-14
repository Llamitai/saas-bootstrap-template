import { getTranslations } from "next-intl/server";
import { AppShell, PermissionGuard } from "@/features/app-shell";
import { type SettingsTab, SettingsView } from "@/features/settings";

interface SettingsPageProps {
  searchParams: Promise<{
    tab?: string | string[];
  }>;
}

function resolveInitialTab(tab: string | string[] | undefined): SettingsTab {
  const value = Array.isArray(tab) ? tab[0] : tab;
  if (value === "security") return value;
  return "general";
}

export default async function SettingsPage({
  searchParams,
}: SettingsPageProps) {
  const [t, params] = await Promise.all([getTranslations("Nav"), searchParams]);

  return (
    <PermissionGuard permission="tenant_settings.view">
      <AppShell
        activePath="/settings"
        breadcrumbItems={[{ label: t("settings") }]}
      >
        <SettingsView initialTab={resolveInitialTab(params.tab)} />
      </AppShell>
    </PermissionGuard>
  );
}
