"use client";

import { Lock, Mail } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { FcGoogle } from "react-icons/fc";

import {
  getAuthErrorMessage,
  loginWithPassword,
} from "@/features/auth/api/auth-api";
import { useSessionActions } from "@/features/auth/model/session-context";
import { AuthContainer } from "@/features/auth/ui/auth-container";
import { Button } from "@/shared/ui/button";
import { SaasLogoMark } from "@/shared/ui/components/saas-logo-mark";
import { Field, FieldContent, FieldError } from "@/shared/ui/field";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";

export function LoginView() {
  const t = useTranslations("Login");
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<{ email?: string; password?: string }>(
    {}
  );
  const [isLoading, setIsLoading] = useState(false);
  const [isGoogleLoading, setIsGoogleLoading] = useState(false);
  const [serverError, setServerError] = useState("");
  const { setSession } = useSessionActions();

  // The Google callback lands back here with ?error= on failure.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("error") === "googleLoginFailed") {
      setServerError(t("errors.googleLoginFailed"));
      window.history.replaceState(null, "", window.location.pathname);
    }
  }, [t]);

  const handleGoogleLogin = () => {
    setIsGoogleLoading(true);
    window.location.assign("/api/auth/google");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const newErrors: { email?: string; password?: string } = {};

    if (!email) {
      newErrors.email = t("errors.emailRequired");
    } else if (!/\S+@\S+\.\S+/.test(email)) {
      newErrors.email = t("errors.emailInvalid");
    }

    if (!password) {
      newErrors.password = t("errors.passwordRequired");
    } else if (password.length < 6) {
      newErrors.password = t("errors.passwordTooShort");
    }

    setErrors(newErrors);

    if (Object.keys(newErrors).length > 0) return;

    setIsLoading(true);
    setServerError("");

    try {
      const result = await loginWithPassword({ email, password });
      setSession(result.user, result.tenant, result.tenantRole, "");
      router.push(result.tenant ? "/members" : "/unassigned");
    } catch (error) {
      setServerError(getAuthErrorMessage(error, t("errors.loginFailed")));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthContainer
      brandMark={<SaasLogoMark className="h-14 w-14 text-foreground" />}
      iconContainerClassName="h-20 w-20"
      title={t("title")}
      description={t("description")}
    >
      <form onSubmit={handleSubmit} className="space-y-5">
        {serverError && (
          <div
            className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive-deep ring-1 ring-destructive/20"
            role="alert"
          >
            {serverError}
          </div>
        )}

        <Field data-invalid={!!errors.email}>
          <Label htmlFor="email" className="text-sm font-semibold">
            {t("emailLabel")}
          </Label>
          <FieldContent>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="email"
                type="email"
                placeholder={t("emailPlaceholder")}
                value={email}
                onValueChange={setEmail}
                aria-invalid={!!errors.email}
                className="pl-10"
                disabled={isLoading}
              />
            </div>
            {errors.email && <FieldError>{errors.email}</FieldError>}
          </FieldContent>
        </Field>

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
                placeholder="********"
                value={password}
                onValueChange={setPassword}
                aria-invalid={!!errors.password}
                className="pl-10"
                disabled={isLoading}
              />
            </div>
            {errors.password && <FieldError>{errors.password}</FieldError>}
          </FieldContent>
        </Field>

        <div>
          <Link
            href="/reset-password"
            className="text-sm text-foreground hover:underline mb-2 block"
          >
            {t("forgotPassword")}
          </Link>
          <Button
            type="submit"
            className="w-full"
            loading={isLoading}
            icon={<Lock />}
          >
            {t("submit")}
          </Button>
        </div>
      </form>

      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <span className="w-full border-t" />
        </div>
        <div className="relative flex justify-center text-sm">
          <span className="bg-background px-3 text-muted-foreground">
            {t("orContinueWith")}
          </span>
        </div>
      </div>

      <Button
        type="button"
        variant="outline"
        className="w-full"
        disabled={isLoading}
        loading={isGoogleLoading}
        onClick={handleGoogleLogin}
      >
        <FcGoogle className="mr-2 h-5 w-5" />
        {t("continueWithGoogle")}
      </Button>

      <div>
        <p className="text-center text-sm text-muted-foreground">
          {t("noAccount")}{" "}
          <Link
            href="/register"
            className="font-semibold text-foreground hover:underline"
          >
            {t("createAccount")}
          </Link>
        </p>
      </div>
    </AuthContainer>
  );
}
