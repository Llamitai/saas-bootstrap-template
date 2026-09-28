import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { PermissionGuard } from "@/features/app-shell";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("PageTitles");
  return { title: t("roles") };
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <PermissionGuard permission="tenant_roles.view">{children}</PermissionGuard>
  );
}
