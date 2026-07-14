"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { usePermissions, useSession } from "@/features/auth";

interface PermissionGuardProps {
  permission: string;
  children: React.ReactNode;
}

export function PermissionGuard({
  permission,
  children,
}: PermissionGuardProps) {
  const { isLoading } = useSession();
  const { hasPermission } = usePermissions();
  const router = useRouter();

  const allowed = hasPermission(permission);

  useEffect(() => {
    if (!isLoading && !allowed) {
      router.replace("/forbidden");
    }
  }, [isLoading, allowed, router]);

  if (isLoading || !allowed) return null;

  return <>{children}</>;
}
