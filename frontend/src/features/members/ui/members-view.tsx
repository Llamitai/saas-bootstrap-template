"use client";

import { AlertCircle, CheckCircle2, UserPlus, Users } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { usePermissions } from "@/features/auth";
import {
  useCancelInvitationMutation,
  useDeleteMemberMutation,
  useInviteMemberMutation,
  useMembersQuery,
  usePendingInvitationsQuery,
  useSendPasswordResetMutation,
  useUpdateMemberMutation,
} from "@/features/members/api/members";
import type {
  InviteMemberPayload,
  TenantUser,
  UpdateTenantUserPayload,
} from "@/features/members/model/types";
import { EditMemberDialog } from "@/features/members/ui/edit-member-dialog";
import { InviteUserDialog } from "@/features/members/ui/invite-user-dialog";
import { MemberItem } from "@/features/members/ui/member-item";
import { PendingInvitationItem } from "@/features/members/ui/pending-invitation-item";
import { useRolesQuery } from "@/features/roles";
import { Button } from "@/shared/ui/button";
import { ConfirmDeleteDialog } from "@/shared/ui/confirm-delete-dialog";
import { EmptyState } from "@/shared/ui/empty-state";
import { PageContent } from "@/shared/ui/page-content";
import { FullPageSpinner } from "@/shared/ui/spinner";

export function MembersView() {
  const t = useTranslations("Members");
  const [deletingUserId, setDeletingUserId] = useState<string | null>(null);
  const [cancelingInvitationId, setCancelingInvitationId] = useState<
    string | null
  >(null);
  const [resetTarget, setResetTarget] = useState<{
    tenantUserId: string;
    email: string;
  } | null>(null);
  const [resetFeedback, setResetFeedback] = useState<{
    tone: "success" | "error";
    message: string;
  } | null>(null);
  const [showInviteDialog, setShowInviteDialog] = useState(false);
  const [editingUserId, setEditingUserId] = useState<string | null>(null);
  const { hasPermission } = usePermissions();
  const canCreate = hasPermission("tenant_users.create");
  const canUpdate = hasPermission("tenant_users.update");

  const { data: members = [], isLoading, error } = useMembersQuery();
  const { data: roles = [] } = useRolesQuery();
  const { data: pendingInvitations = [] } = usePendingInvitationsQuery();
  const inviteMutation = useInviteMemberMutation();
  const updateMutation = useUpdateMemberMutation();
  const deleteMutation = useDeleteMemberMutation();
  const cancelInvitationMutation = useCancelInvitationMutation();
  const sendResetMutation = useSendPasswordResetMutation();

  const handleInvite = async (payload: InviteMemberPayload) => {
    await inviteMutation.mutateAsync(payload);
    setShowInviteDialog(false);
  };

  const handleRoleChange = async (uuid: string, roleId: string) => {
    await updateMutation.mutateAsync({
      uuid,
      payload: { tenantRoleId: roleId },
    });
  };

  const handleEditSubmit = async (
    uuid: string,
    payload: UpdateTenantUserPayload
  ) => {
    await updateMutation.mutateAsync({ uuid, payload });
  };

  const handleDeleteConfirm = async () => {
    if (!deletingUserId) return;
    await deleteMutation.mutateAsync(deletingUserId);
    setDeletingUserId(null);
  };

  const handleCancelConfirm = async () => {
    if (!cancelingInvitationId) return;
    await cancelInvitationMutation.mutateAsync(cancelingInvitationId);
    setCancelingInvitationId(null);
  };

  const handleSendResetConfirm = async () => {
    if (!resetTarget) return;
    const { tenantUserId, email } = resetTarget;
    setResetTarget(null);
    try {
      const result = await sendResetMutation.mutateAsync(tenantUserId);
      setResetFeedback({
        tone: "success",
        message: t("resetSuccess", { email: result.email ?? email }),
      });
    } catch (e) {
      setResetFeedback({
        tone: "error",
        message: e instanceof Error ? e.message : t("resetError"),
      });
    }
  };

  const deletingUser = deletingUserId
    ? members.find((m: TenantUser) => m.uuid === deletingUserId)
    : null;
  const editingUser = editingUserId
    ? (members.find((m: TenantUser) => m.uuid === editingUserId) ?? null)
    : null;
  const cancelingInvitation = cancelingInvitationId
    ? pendingInvitations.find((i) => i.uuid === cancelingInvitationId)
    : null;

  if (isLoading) return <FullPageSpinner />;

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-100">
        <div className="text-destructive">{error.message}</div>
      </div>
    );
  }

  const inviteDialog = (
    <InviteUserDialog
      open={showInviteDialog}
      onOpenChange={setShowInviteDialog}
      onSubmit={handleInvite}
      roles={roles}
    />
  );

  const hasMembers = members.length > 0;
  const hasPending = pendingInvitations.length > 0;

  if (!hasMembers && !hasPending) {
    return (
      <>
        <PageContent>
          <PageContent.Header
            icon={Users}
            title={t("title")}
            subtitle={t("description")}
            className="px-0 pt-0"
          />
          <PageContent.Body className="items-center justify-center px-0 pb-0">
            <EmptyState
              icon={Users}
              title={t("emptyTitle")}
              description={t("emptyDescription")}
              actionLabel={canCreate ? t("inviteMember") : undefined}
              onAction={canCreate ? () => setShowInviteDialog(true) : undefined}
            />
          </PageContent.Body>
        </PageContent>
        {inviteDialog}
      </>
    );
  }

  return (
    <>
      <PageContent>
        <PageContent.Header
          icon={Users}
          title={t("title")}
          subtitle={t("description")}
          className="px-0 pt-0"
          actions={
            <Button
              onClick={() => setShowInviteDialog(true)}
              className="gap-2"
              disabled={!canCreate}
            >
              <UserPlus className="h-4 w-4" />
              {t("invite")}
            </Button>
          }
        />
        <PageContent.Body className="gap-6 px-0 pb-0">
          {hasPending && (
            <section className="flex flex-col gap-2">
              <h3 className="text-sm font-semibold text-muted-foreground">
                {t("pendingTitle", { count: pendingInvitations.length })}
              </h3>
              {pendingInvitations.map((inv) => (
                <PendingInvitationItem
                  key={inv.uuid}
                  invitation={inv}
                  roles={roles}
                  onCancel={setCancelingInvitationId}
                />
              ))}
            </section>
          )}

          <section className="flex flex-col gap-2">
            {hasPending && (
              <h3 className="text-sm font-semibold text-muted-foreground">
                {t("activeTitle", { count: members.length })}
              </h3>
            )}
            {members.map((member: TenantUser) => (
              <MemberItem
                key={member.uuid}
                member={member}
                roles={roles}
                onRoleChange={handleRoleChange}
                onRemove={setDeletingUserId}
                onSendResetPassword={(tenantUserId, email) =>
                  setResetTarget({ tenantUserId, email })
                }
                onEdit={setEditingUserId}
              />
            ))}
          </section>
        </PageContent.Body>
      </PageContent>

      {inviteDialog}

      <EditMemberDialog
        member={editingUser}
        roles={roles}
        open={editingUserId !== null}
        onOpenChange={(open) => {
          if (!open) setEditingUserId(null);
        }}
        onSubmit={handleEditSubmit}
        canEditRole={canUpdate}
      />

      <ConfirmDeleteDialog
        open={deletingUserId !== null}
        onOpenChange={(open) => {
          if (!open) setDeletingUserId(null);
        }}
        onConfirm={handleDeleteConfirm}
        title={t("deleteTitle")}
        description={
          deletingUser
            ? t("deleteDescription", {
                name: `${deletingUser.firstName} ${deletingUser.lastName}`,
              })
            : t("deleteFallback")
        }
      />

      <ConfirmDeleteDialog
        open={cancelingInvitationId !== null}
        onOpenChange={(open) => {
          if (!open) setCancelingInvitationId(null);
        }}
        onConfirm={handleCancelConfirm}
        title={t("cancelInviteTitle")}
        description={
          cancelingInvitation
            ? t("cancelInviteDescription", {
                email: cancelingInvitation.email,
              })
            : t("cancelInviteFallback")
        }
      />

      <ConfirmDeleteDialog
        open={resetTarget !== null}
        onOpenChange={(open) => {
          if (!open) setResetTarget(null);
        }}
        onConfirm={handleSendResetConfirm}
        title={t("resetTitle")}
        description={
          resetTarget
            ? t("resetDescription", { email: resetTarget.email })
            : t("resetFallback")
        }
        confirmLabel={t("resetConfirm")}
        variant="primary"
      />

      {resetFeedback ? (
        <ResetFeedbackToast
          message={resetFeedback.message}
          tone={resetFeedback.tone}
          onDismiss={() => setResetFeedback(null)}
        />
      ) : null}
    </>
  );
}

interface ResetFeedbackToastProps {
  message: string;
  tone: "success" | "error";
  onDismiss: () => void;
}

function ResetFeedbackToast({
  message,
  tone,
  onDismiss,
}: ResetFeedbackToastProps) {
  const t = useTranslations("Members");
  useEffect(() => {
    const timer = setTimeout(onDismiss, 4500);
    return () => clearTimeout(timer);
  }, [onDismiss]);

  const Icon = tone === "success" ? CheckCircle2 : AlertCircle;
  const colorClass = tone === "success" ? "text-primary" : "text-destructive";

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed right-6 bottom-6 z-50 flex max-w-sm items-start gap-3 rounded-lg bg-card px-4 py-3 text-sm shadow-overlay ring-1 ring-border"
    >
      <Icon className={`h-5 w-5 shrink-0 mt-px ${colorClass}`} />
      <p className="flex-1 leading-snug">{message}</p>
      <button
        type="button"
        className="text-muted-foreground hover:text-foreground -mr-1 px-1"
        onClick={onDismiss}
        aria-label={t("closeAria")}
      >
        ×
      </button>
    </div>
  );
}
