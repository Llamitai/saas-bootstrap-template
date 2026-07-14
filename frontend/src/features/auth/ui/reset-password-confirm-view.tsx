"use client";

import { CheckCircle, KeyRound, Lock } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useState } from "react";

import {
  confirmPasswordReset,
  getAuthErrorCode,
  getAuthErrorMessage,
} from "@/features/auth/api/auth-api";
import { AuthContainer } from "@/features/auth/ui/auth-container";
import { Button, buttonVariants } from "@/shared/ui/button";
import { Field, FieldContent, FieldError } from "@/shared/ui/field";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";

export function ResetPasswordConfirmView({ token }: { token: string }) {
  const t = useTranslations("ResetPasswordToken");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [errors, setErrors] = useState<{
    password?: string;
    confirm?: string;
  }>({});
  const [serverError, setServerError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const next: typeof errors = {};
    if (password.length < 8) next.password = t("errors.passwordTooShort");
    if (password !== confirm) next.confirm = t("errors.passwordsDontMatch");
    setErrors(next);
    if (Object.keys(next).length > 0) return;

    setIsLoading(true);
    setServerError("");
    try {
      await confirmPasswordReset(token, password);
      setSuccess(true);
    } catch (error) {
      if (getAuthErrorCode(error) === "common.InvalidOrExpiredToken") {
        setServerError(t("invalidLink"));
      } else {
        setServerError(getAuthErrorMessage(error, t("errors.requestFailed")));
      }
    } finally {
      setIsLoading(false);
    }
  };

  if (success) {
    return (
      <AuthContainer
        icon={CheckCircle}
        title={t("successTitle")}
        description={t("successDescription")}
      >
        <Link
          href="/"
          className={buttonVariants({ className: "w-full font-semibold" })}
        >
          {t("signIn")}
        </Link>
      </AuthContainer>
    );
  }

  return (
    <AuthContainer
      icon={KeyRound}
      title={t("title")}
      description={t("description")}
    >
      <form onSubmit={handleSubmit} className="space-y-5">
        <Field data-invalid={!!errors.password}>
          <Label htmlFor="password" className="text-sm font-semibold">
            {t("passwordLabel")}
          </Label>
          <FieldContent>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="password"
                type="password"
                value={password}
                onValueChange={setPassword}
                aria-invalid={!!errors.password}
                minLength={8}
                className="pl-10"
                autoFocus
              />
            </div>
            {errors.password && <FieldError>{errors.password}</FieldError>}
          </FieldContent>
        </Field>

        <Field data-invalid={!!errors.confirm}>
          <Label htmlFor="confirm" className="text-sm font-semibold">
            {t("confirmPasswordLabel")}
          </Label>
          <FieldContent>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="confirm"
                type="password"
                value={confirm}
                onValueChange={setConfirm}
                aria-invalid={!!errors.confirm}
                minLength={8}
                className="pl-10"
              />
            </div>
            {errors.confirm && <FieldError>{errors.confirm}</FieldError>}
          </FieldContent>
        </Field>

        {serverError ? (
          <p className="text-sm text-destructive" role="alert">
            {serverError}
          </p>
        ) : null}

        <Button
          type="submit"
          loading={isLoading}
          icon={<KeyRound />}
          className="w-full bg-foreground text-background hover:bg-foreground/90 font-semibold"
        >
          {t("submit")}
        </Button>
      </form>

      <div>
        <p className="text-center text-sm text-muted-foreground">
          <Link
            href="/reset-password"
            className="font-semibold text-foreground hover:underline"
          >
            {t("requestNew")}
          </Link>
        </p>
      </div>
    </AuthContainer>
  );
}
