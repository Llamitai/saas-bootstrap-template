"use client";

import { Plus, Shield } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { usePermissions } from "@/features/auth";
import {
  useCreateRoleMutation,
  useDeleteRoleMutation,
  useRolesQuery,
  useUpdateRoleMutation,
} from "@/features/roles/api/roles";
import type {
  CreateTenantRolePayload,
  TenantRole,
  UpdateTenantRolePayload,
} from "@/features/roles/model/types";
import { CreateRoleDialog } from "@/features/roles/ui/create-role-dialog";
import { EditRoleDialog } from "@/features/roles/ui/edit-role-dialog";
import { RoleCard } from "@/features/roles/ui/role-card";
import { Button } from "@/shared/ui/button";
import { ConfirmDeleteDialog } from "@/shared/ui/confirm-delete-dialog";
import { EmptyState } from "@/shared/ui/empty-state";
import { PageContent } from "@/shared/ui/page-content";
import { FullPageSpinner } from "@/shared/ui/spinner";

export function RolesView() {
  const t = useTranslations("Roles");
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [editingRole, setEditingRole] = useState<TenantRole | null>(null);
  const [deletingRoleId, setDeletingRoleId] = useState<string | null>(null);
  const { hasPermission } = usePermissions();
  const canCreate = hasPermission("tenant_roles.create");

  const { data: roles = [], isLoading, error } = useRolesQuery();
  const createMutation = useCreateRoleMutation();
  const updateMutation = useUpdateRoleMutation();
  const deleteMutation = useDeleteRoleMutation();

  const handleCreate = async (payload: CreateTenantRolePayload) => {
    await createMutation.mutateAsync(payload);
    setShowCreateDialog(false);
  };

  const handleEdit = (uuid: string) => {
    const role = roles.find((r: TenantRole) => r.uuid === uuid);
    if (role) setEditingRole(role);
  };

  const handleEditSubmit = async (
    uuid: string,
    payload: UpdateTenantRolePayload
  ) => {
    await updateMutation.mutateAsync({ uuid, payload });
    setEditingRole(null);
  };

  const handleDeleteConfirm = async () => {
    if (!deletingRoleId) return;
    await deleteMutation.mutateAsync(deletingRoleId);
    setDeletingRoleId(null);
  };

  const deletingRole = deletingRoleId
    ? roles.find((r: TenantRole) => r.uuid === deletingRoleId)
    : null;

  const dialogs = (
    <>
      <CreateRoleDialog
        open={showCreateDialog}
        onOpenChange={setShowCreateDialog}
        onSubmit={handleCreate}
      />
      <EditRoleDialog
        role={editingRole}
        open={editingRole !== null}
        onOpenChange={(open) => {
          if (!open) setEditingRole(null);
        }}
        onSubmit={handleEditSubmit}
      />
      <ConfirmDeleteDialog
        open={deletingRoleId !== null}
        onOpenChange={(open) => {
          if (!open) setDeletingRoleId(null);
        }}
        onConfirm={handleDeleteConfirm}
        title={t("deleteTitle")}
        description={
          deletingRole
            ? t("deleteDescription", { name: deletingRole.name })
            : t("deleteDescriptionFallback")
        }
      />
    </>
  );

  if (isLoading) return <FullPageSpinner />;

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-100">
        <div className="text-destructive">{error.message}</div>
      </div>
    );
  }

  if (roles.length === 0) {
    return (
      <>
        <PageContent>
          <PageContent.Header
            icon={Shield}
            title={t("title")}
            subtitle={t("description")}
            className="px-0 pt-0"
          />
          <PageContent.Body className="items-center justify-center px-0 pb-0">
            <EmptyState
              icon={Shield}
              title={t("emptyTitle")}
              description={t("emptyDescription")}
              actionLabel={canCreate ? t("create") : undefined}
              onAction={canCreate ? () => setShowCreateDialog(true) : undefined}
            />
          </PageContent.Body>
        </PageContent>
        {dialogs}
      </>
    );
  }

  return (
    <>
      <PageContent>
        <PageContent.Header
          icon={Shield}
          title={t("title")}
          subtitle={t("description")}
          className="px-0 pt-0"
          actions={
            <Button
              onClick={() => setShowCreateDialog(true)}
              className="gap-2"
              disabled={!canCreate}
            >
              <Plus className="h-4 w-4" />
              {t("create")}
            </Button>
          }
        />
        <PageContent.Body className="px-0 pb-0">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {roles.map((role: TenantRole) => (
              <RoleCard
                key={role.uuid}
                role={role}
                onEdit={handleEdit}
                onDelete={setDeletingRoleId}
              />
            ))}
          </div>
        </PageContent.Body>
      </PageContent>
      {dialogs}
    </>
  );
}
