"use client";

import { useTranslations } from "next-intl";
import { AppShell, PermissionGuard } from "@/features/app-shell";
import { RolesView } from "@/features/roles";

export default function RolesPage() {
  const t = useTranslations("Nav");
  return (
    <PermissionGuard permission="tenant_roles.view">
      <AppShell activePath="/roles" breadcrumbItems={[{ label: t("roles") }]}>
        <RolesView />
      </AppShell>
    </PermissionGuard>
  );
}
