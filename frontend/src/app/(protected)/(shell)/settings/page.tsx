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
  const params = await searchParams;
  return <SettingsView initialTab={resolveInitialTab(params.tab)} />;
}
