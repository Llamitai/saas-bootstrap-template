import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { PermissionGuard } from "@/features/app-shell";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("PageTitles");
  return { title: t("members") };
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <PermissionGuard permission="tenant_users.view">{children}</PermissionGuard>
  );
}
