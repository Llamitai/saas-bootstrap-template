"use client";

import {
  Copy,
  FileText,
  Image as ImageIcon,
  Key,
  type LucideIcon,
  Pencil,
  Settings,
  ShieldAlert,
  Trash2,
  Upload,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import type { ChangeEvent, ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import { usePermissions, useSessionStore } from "@/features/auth";
import {
  useDeleteTenantMutation,
  useSettingsQuery,
  useUpdateAvatarMutation,
  useUpdateSettingsMutation,
} from "@/features/settings/api/settings";
import { ActionButton } from "@/shared/ui/action-button";
import { Avatar, AvatarFallback, AvatarImage } from "@/shared/ui/avatar";
import { Button } from "@/shared/ui/button";
import { Card } from "@/shared/ui/card";
import { ConfirmDeleteDialog } from "@/shared/ui/confirm-delete-dialog";
import { Input } from "@/shared/ui/input";
import { LineIcon } from "@/shared/ui/line-icon";
import { PageContent } from "@/shared/ui/page-content";
import { FullPageSpinner } from "@/shared/ui/spinner";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/ui/tabs";

export type SettingsTab = "general" | "security";

interface SettingsViewProps {
  initialTab?: SettingsTab;
}

interface SettingsRowProps {
  icon: LucideIcon;
  title: string;
  description: ReactNode;
  children: ReactNode;
}

function writeSettingsTabToUrl(tab: SettingsTab) {
  if (typeof window === "undefined") return;

  const url = new URL(window.location.href);
  if (tab === "general") {
    url.searchParams.delete("tab");
  } else {
    url.searchParams.set("tab", tab);
  }
  window.history.replaceState(null, "", `${url.pathname}${url.search}`);
}

function coerceSettingsTab(value: string): SettingsTab {
  if (value === "security") return value;
  return "general";
}

function SettingsRow({
  icon: Icon,
  title,
  description,
  children,
}: SettingsRowProps) {
  return (
    <div className="grid gap-4 border-b border-border/70 px-5 py-5 last:border-b-0 sm:grid-cols-[2.5rem_minmax(0,1fr)_auto] sm:items-center sm:px-6">
      <div className="flex size-10 items-center justify-center rounded-lg bg-muted text-muted-foreground">
        <Icon className="size-5" />
      </div>
      <div className="min-w-0 space-y-1">
        <h3 className="text-sm font-medium">{title}</h3>
        <p className="max-w-2xl text-sm text-muted-foreground">{description}</p>
      </div>
      <div className="min-w-0 sm:justify-self-end">{children}</div>
    </div>
  );
}

function SettingsSection({ children }: { children: ReactNode }) {
  return <Card className="gap-0 p-0">{children}</Card>;
}

interface CopyFieldProps {
  value: string;
  inputClassName?: string;
  copyLabel: string;
}

function CopyField({ value, inputClassName, copyLabel }: CopyFieldProps) {
  return (
    <div className="flex min-w-0 gap-2">
      <Input value={value} readOnly className={inputClassName} />
      <Button
        type="button"
        variant="outline"
        size="icon"
        icon={<Copy />}
        aria-label={copyLabel}
        onClick={() => void navigator.clipboard.writeText(value)}
      />
    </div>
  );
}

export function SettingsView({ initialTab = "general" }: SettingsViewProps) {
  const t = useTranslations("Settings");
  const router = useRouter();
  const { hasPermission } = usePermissions();
  const canUpdateSettings = hasPermission("tenant_settings.update");
  const canDeleteTenant = hasPermission("tenant_settings.delete");
  const clearTenant = useSessionStore((s) => s.clearTenant);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [activeTab, setActiveTab] = useState<SettingsTab>(initialTab);
  const [localName, setLocalName] = useState("");
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const { data: settings, isLoading } = useSettingsQuery();
  const updateSettings = useUpdateSettingsMutation();
  const uploadAvatar = useUpdateAvatarMutation();
  const deleteTenant = useDeleteTenantMutation();

  useEffect(() => {
    setActiveTab(initialTab);
  }, [initialTab]);

  useEffect(() => {
    const cannotUseSecurity = activeTab === "security" && !canDeleteTenant;

    if (cannotUseSecurity) {
      setActiveTab("general");
      writeSettingsTabToUrl("general");
    }
  }, [activeTab, canDeleteTenant]);

  useEffect(() => {
    if (settings) setLocalName(settings.name);
  }, [settings]);

  const handleTabChange = (value: string) => {
    const nextTab = coerceSettingsTab(value);
    if (nextTab === "security" && !canDeleteTenant) return;

    setActiveTab(nextTab);
    writeSettingsTabToUrl(nextTab);
  };

  const handleNameBlur = () => {
    if (
      canUpdateSettings &&
      settings &&
      localName.trim() &&
      localName !== settings.name
    ) {
      updateSettings.mutate(localName.trim());
    }
  };

  const handleAvatarChange = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (canUpdateSettings && file) uploadAvatar.mutate(file);
  };

  const handleDeleteConfirm = async () => {
    if (!canDeleteTenant) return;

    setIsDeleting(true);
    try {
      await deleteTenant.mutateAsync();
      clearTenant();
      router.push("/unassigned");
    } catch {
      setIsDeleting(false);
    }
  };

  if (isLoading) return <FullPageSpinner />;

  if (!settings) {
    return (
      <PageContent>
        <PageContent.Header
          icon={Settings}
          title={t("title")}
          subtitle={t("description")}
          className="px-0 pt-0"
        />
        <PageContent.Body className="items-center justify-center px-0 pb-0">
          <div className="text-muted-foreground">{t("notFound")}</div>
        </PageContent.Body>
      </PageContent>
    );
  }

  return (
    <>
      <PageContent>
        <Tabs
          value={activeTab}
          onValueChange={handleTabChange}
          className="flex min-h-0 flex-1 flex-col"
        >
          <PageContent.Header
            icon={Settings}
            title={t("title")}
            subtitle={t("description")}
            className="px-0 pt-0"
          />

          <div className="mb-5 flex shrink-0 items-center justify-between gap-3">
            <div className="min-w-0 overflow-x-auto">
              <TabsList>
                <TabsTrigger value="general">
                  <LineIcon name="settings" size={18} />
                  {t("tabs.general")}
                </TabsTrigger>
                {canDeleteTenant ? (
                  <TabsTrigger value="security">
                    <LineIcon name="permissions" size={18} />
                    {t("tabs.security")}
                  </TabsTrigger>
                ) : null}
              </TabsList>
            </div>
          </div>

          <PageContent.Body className="px-0 pb-0">
            <TabsContent value="general" className="mt-0">
              <SettingsSection>
                <SettingsRow
                  icon={Pencil}
                  title={t("orgName.title")}
                  description={t("orgName.description")}
                >
                  <Input
                    value={localName}
                    onChange={(e) => setLocalName(e.target.value)}
                    onBlur={handleNameBlur}
                    placeholder={t("orgName.placeholder")}
                    readOnly={!canUpdateSettings}
                    disabled={!canUpdateSettings}
                    className="w-full sm:w-64"
                  />
                </SettingsRow>

                <SettingsRow
                  icon={ImageIcon}
                  title={t("orgAvatar.title")}
                  description={t("orgAvatar.description")}
                >
                  <div className="flex items-center gap-3">
                    <Avatar className="size-10">
                      {settings.avatar ? (
                        <AvatarImage src={settings.avatar} />
                      ) : null}
                      <AvatarFallback className="font-semibold">
                        {settings.name.charAt(0).toUpperCase()}
                      </AvatarFallback>
                    </Avatar>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="image/*"
                      className="hidden"
                      onChange={handleAvatarChange}
                    />
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      icon={<Upload />}
                      loading={uploadAvatar.isPending}
                      disabled={!canUpdateSettings}
                      onClick={() => fileInputRef.current?.click()}
                    >
                      {t("orgAvatar.upload")}
                    </Button>
                  </div>
                </SettingsRow>

                <SettingsRow
                  icon={Key}
                  title={t("orgId.title")}
                  description={t("orgId.description")}
                >
                  <CopyField
                    value={settings.tenantId}
                    copyLabel={t("orgId.copy")}
                    inputClassName="w-full font-mono text-xs sm:w-48"
                  />
                </SettingsRow>

                <SettingsRow
                  icon={FileText}
                  title={t("maxPages.title")}
                  description={
                    <>
                      {t("maxPages.description")}{" "}
                      <a href="#" className="text-primary hover:underline">
                        {t("maxPages.descriptionLink")}
                      </a>{" "}
                      {t("maxPages.descriptionTail")}
                    </>
                  }
                >
                  <div className="text-sm font-medium text-muted-foreground">
                    {t("maxPages.value", { count: settings.maxPages })}
                  </div>
                </SettingsRow>
              </SettingsSection>
            </TabsContent>

            {canDeleteTenant ? (
              <TabsContent value="security" className="mt-0">
                <SettingsSection>
                  <SettingsRow
                    icon={ShieldAlert}
                    title={t("dangerZone.title")}
                    description={t("dangerZone.description")}
                  >
                    <ActionButton
                      type="button"
                      variant="destructive"
                      loading={isDeleting}
                      icon={<Trash2 />}
                      onClick={() => setDeleteDialogOpen(true)}
                    >
                      {t("deleteOrg", { name: settings.name })}
                    </ActionButton>
                  </SettingsRow>
                </SettingsSection>
              </TabsContent>
            ) : null}
          </PageContent.Body>
        </Tabs>
      </PageContent>

      <ConfirmDeleteDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        onConfirm={() => void handleDeleteConfirm()}
        title={t("deleteTitle")}
        description={t("deleteDescription", { name: settings.name })}
        confirmLabel={t("deleteConfirmLabel")}
        cancelLabel={t("deleteCancelLabel")}
      />
    </>
  );
}
