"use client";

import { Pencil, Shield, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { TenantRoleStatus } from "@/entities/tenant";
import { usePermissions } from "@/features/auth";
import type { TenantRole } from "@/features/roles/model/types";
import { cn } from "@/shared/lib/utils";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { StatusBadge } from "@/shared/ui/status-badge";

interface RoleCardProps {
  role: TenantRole;
  onEdit: (uuid: string) => void;
  onDelete: (uuid: string) => void;
}

export function RoleCard({ role, onEdit, onDelete }: RoleCardProps) {
  const t = useTranslations("RoleCard");
  const { hasPermission } = usePermissions();
  const canUpdate = hasPermission("tenant_roles.update");
  const canDelete = hasPermission("tenant_roles.delete");

  const handleEdit = () => {
    if (canUpdate) onEdit(role.uuid);
  };

  return (
    <Card
      interactive={canUpdate}
      className={cn(
        "relative flex-row items-center gap-4 px-4 py-3",
        canUpdate && "focus-within:bg-muted/30"
      )}
    >
      {canUpdate ? (
        <button
          type="button"
          aria-label={t("editAria", { name: role.name })}
          className="absolute inset-0 z-0 rounded-lg focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-primary/50"
          onClick={handleEdit}
        />
      ) : null}
      <div
        className={cn(
          "relative z-10 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted",
          canUpdate && "pointer-events-none"
        )}
      >
        <Shield className="h-4 w-4 text-muted-foreground" />
      </div>
      <div
        className={cn(
          "relative z-10 flex-1 min-w-0",
          canUpdate && "pointer-events-none"
        )}
      >
        <h3 className="text-sm font-semibold truncate">{role.name}</h3>
        <div className="flex items-center gap-2 mt-1.5">
          <StatusBadge
            tone={
              role.status === TenantRoleStatus.ACTIVE ? "success" : "neutral"
            }
            status={role.status}
            size="sm"
          >
            {role.status === TenantRoleStatus.ACTIVE
              ? t("active")
              : t("inactive")}
          </StatusBadge>
          <span className="text-xs text-muted-foreground">
            {t("permissions", { count: role.permissions.length })}
          </span>
        </div>
      </div>
      <div className="relative z-10 flex items-center gap-1 shrink-0">
        <Button
          variant="ghost"
          size="icon-xs"
          aria-label={t("editAria", { name: role.name })}
          onClick={handleEdit}
          disabled={!canUpdate}
        >
          <Pencil className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon-xs"
          aria-label={t("deleteAria", { name: role.name })}
          onClick={() => onDelete(role.uuid)}
          disabled={!canDelete}
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>
    </Card>
  );
}
