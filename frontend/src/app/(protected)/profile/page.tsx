"use client";

import { useTranslations } from "next-intl";
import { AppShell } from "@/features/app-shell";
import { ProfileView } from "@/features/profile";

export default function ProfilePage() {
  const t = useTranslations("NavUser");
  return (
    <AppShell activePath="/profile" breadcrumbItems={[{ label: t("profile") }]}>
      <ProfileView />
    </AppShell>
  );
}
