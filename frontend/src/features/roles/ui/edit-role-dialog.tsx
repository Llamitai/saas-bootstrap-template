"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { TenantRoleStatus } from "@/entities/tenant";
import type {
  TenantRole,
  UpdateTenantRolePayload,
} from "@/features/roles/model/types";
import { PermissionSelector } from "@/features/roles/ui/permission-selector";
import { SelectedPermissions } from "@/features/roles/ui/selected-permissions";
import { ActionButton } from "@/shared/ui/action-button";
import { Button } from "@/shared/ui/button";
import {
  Dialog,
  DialogBackdrop,
  DialogFooter,
  DialogHeader,
  DialogPopup,
  DialogTitle,
} from "@/shared/ui/dialog";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/ui/select";

interface EditRoleDialogProps {
  role: TenantRole | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (uuid: string, payload: UpdateTenantRolePayload) => Promise<void>;
}

export function EditRoleDialog({
  role,
  open,
  onOpenChange,
  onSubmit,
}: EditRoleDialogProps) {
  const t = useTranslations("RoleDialog");
  const [name, setName] = useState("");
  const [status, setStatus] = useState<TenantRoleStatus>(
    TenantRoleStatus.ACTIVE
  );
  const [permissions, setPermissions] = useState<string[]>([]);
  const [showPermissionSelector, setShowPermissionSelector] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (role) {
      setName(role.name);
      setStatus(role.status);
      setPermissions(role.permissions.map((p) => p.code));
    }
  }, [role]);

  const canSubmit = name.trim().length > 0 && !isSubmitting;

  const handleSubmit = async () => {
    if (!canSubmit || !role) return;
    setIsSubmitting(true);
    try {
      await onSubmit(role.uuid, {
        name: name.trim(),
        permissions,
        status,
      });
      onOpenChange(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRemovePermission = (code: string) => {
    setPermissions((prev) => prev.filter((c) => c !== code));
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogBackdrop />
        <DialogPopup className="max-w-md p-6">
          <DialogHeader>
            <DialogTitle>{t("editTitle")}</DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="edit-role-name">{t("nameLabel")}</Label>
              <Input
                id="edit-role-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleSubmit();
                }}
                autoFocus
              />
            </div>

            <div className="space-y-2">
              <Label>{t("status")}</Label>
              <Select
                value={status}
                onValueChange={(val) => setStatus(val as TenantRoleStatus)}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={TenantRoleStatus.ACTIVE}>
                    {t("statusActive")}
                  </SelectItem>
                  <SelectItem value={TenantRoleStatus.INACTIVE}>
                    {t("statusInactive")}
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>{t("permissions")}</Label>
              <Button
                variant="outline"
                className="w-full"
                onClick={() => setShowPermissionSelector(true)}
                type="button"
              >
                {t("selectPermissions")}
              </Button>
              <div className="mt-2">
                <SelectedPermissions
                  permissions={permissions}
                  onRemove={handleRemovePermission}
                />
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isSubmitting}
            >
              {t("cancel")}
            </Button>
            <ActionButton
              onClick={handleSubmit}
              disabled={!canSubmit}
              loading={isSubmitting}
            >
              {t("save")}
            </ActionButton>
          </DialogFooter>
        </DialogPopup>
      </Dialog>

      <PermissionSelector
        open={showPermissionSelector}
        onOpenChange={setShowPermissionSelector}
        selected={permissions}
        onConfirm={setPermissions}
      />
    </>
  );
}
