"use client";

import { useTranslations } from "next-intl";
import { AppShell, PermissionGuard } from "@/features/app-shell";
import { MembersView } from "@/features/members";

export default function MembersPage() {
  const t = useTranslations("Nav");
  return (
    <PermissionGuard permission="tenant_users.view">
      <AppShell
        activePath="/members"
        breadcrumbItems={[{ label: t("members") }]}
      >
        <MembersView />
      </AppShell>
    </PermissionGuard>
  );
}
