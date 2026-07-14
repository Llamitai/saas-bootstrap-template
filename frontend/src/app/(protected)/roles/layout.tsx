import type { Metadata } from "next";
import { PermissionGuard } from "@/features/app-shell";

export const metadata: Metadata = {
  title: "Roles",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <PermissionGuard permission="tenant_roles.view">{children}</PermissionGuard>
  );
}
