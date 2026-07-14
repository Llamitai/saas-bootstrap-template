"use client";

import { User } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { useProfileStore } from "@/features/profile/model/profile-store";
import { ActionButton } from "@/shared/ui/action-button";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { PageContent } from "@/shared/ui/page-content";

export function ProfileView() {
  const t = useTranslations("Profile");
  const {
    profile,
    isLoading,
    isSaving,
    isChangingPassword,
    saveError,
    saveSuccess,
    passwordError,
    passwordSuccess,
    loadProfile,
    updateProfile,
    updatePassword,
    clearFeedback,
  } = useProfileStore();

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [confirmPasswordError, setConfirmPasswordError] = useState("");

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  useEffect(() => {
    if (profile) {
      setFirstName(profile.firstName ?? "");
      setLastName(profile.lastName ?? "");
    }
  }, [profile]);

  useEffect(() => {
    if (passwordSuccess) {
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setConfirmPasswordError("");
    }
  }, [passwordSuccess]);

  const handleProfileSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    clearFeedback();
    updateProfile({ firstName, lastName });
  };

  const handlePasswordSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    clearFeedback();

    if (newPassword !== confirmPassword) {
      setConfirmPasswordError(t("passwordsDontMatch"));
      return;
    }
    setConfirmPasswordError("");
    updatePassword({ currentPassword, newPassword });
  };

  const email = profile?.emailAddress?.email ?? "";
  const isVerified = profile?.emailAddress?.isVerified ?? false;

  if (isLoading) {
    return (
      <PageContent>
        <PageContent.Header
          icon={User}
          title={t("title")}
          subtitle={t("description")}
          className="px-0 pt-0"
        />
        <PageContent.Body className="items-center justify-center px-0 pb-0">
          <div className="text-muted-foreground">{t("loading")}</div>
        </PageContent.Body>
      </PageContent>
    );
  }

  return (
    <PageContent>
      <PageContent.Header
        icon={User}
        title={t("title")}
        subtitle={t("description")}
        className="px-0 pt-0"
      />
      <PageContent.Body className="max-w-2xl gap-8 px-0 pb-0">
        <form onSubmit={handleProfileSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="email">{t("email")}</Label>
            <Input id="email" value={email} readOnly className="bg-muted" />
            {isVerified && (
              <p className="text-xs text-success-deep">{t("emailVerified")}</p>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="firstName">{t("firstName")}</Label>
            <Input
              id="firstName"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              placeholder={t("firstNamePlaceholder")}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="lastName">{t("lastName")}</Label>
            <Input
              id="lastName"
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              placeholder={t("lastNamePlaceholder")}
            />
          </div>

          {saveError && <p className="text-sm text-destructive">{saveError}</p>}
          {saveSuccess && (
            <p className="text-sm text-success-deep">{t("saveSuccess")}</p>
          )}

          <div>
            <ActionButton type="submit" loading={isSaving}>
              {isSaving ? t("saving") : t("save")}
            </ActionButton>
          </div>
        </form>

        <div className="border border-destructive rounded-lg p-6 flex flex-col gap-4">
          <div>
            <h3 className="text-lg font-semibold text-destructive">
              {t("dangerZone")}
            </h3>
            <p className="text-sm text-muted-foreground mt-1">
              {t("dangerZoneDescription")}
            </p>
          </div>

          <form onSubmit={handlePasswordSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="currentPassword">{t("currentPassword")}</Label>
              <Input
                id="currentPassword"
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                placeholder={t("currentPasswordPlaceholder")}
                required
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="newPassword">{t("newPassword")}</Label>
              <Input
                id="newPassword"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder={t("newPasswordPlaceholder")}
                required
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="confirmPassword">{t("confirmPassword")}</Label>
              <Input
                id="confirmPassword"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder={t("confirmPasswordPlaceholder")}
                required
              />
              {confirmPasswordError && (
                <p className="text-xs text-destructive">
                  {confirmPasswordError}
                </p>
              )}
            </div>

            {passwordError && (
              <p className="text-sm text-destructive">{passwordError}</p>
            )}
            {passwordSuccess && (
              <p className="text-sm text-success-deep">
                {t("passwordSuccess")}
              </p>
            )}

            <div>
              <ActionButton
                type="submit"
                variant="destructive"
                loading={isChangingPassword}
              >
                {isChangingPassword ? t("changing") : t("changePassword")}
              </ActionButton>
            </div>
          </form>
        </div>
      </PageContent.Body>
    </PageContent>
  );
}
