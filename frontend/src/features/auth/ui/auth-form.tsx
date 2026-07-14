"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { useForm } from "react-hook-form";

import {
  type LoginFormData,
  loginFormSchema,
} from "@/features/auth/model/types";
import { ActionButton } from "@/shared/ui/action-button";
import { Button } from "@/shared/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/shared/ui/card";
import {
  Field,
  FieldContent,
  FieldError,
  FieldGroup,
  FieldTitle,
} from "@/shared/ui/field";
import { Input } from "@/shared/ui/input";

interface AuthFormProps {
  onSubmit: (data: LoginFormData) => Promise<void>;
  isLoading?: boolean;
  error?: string;
}

export function AuthForm({
  onSubmit,
  isLoading = false,
  error,
}: AuthFormProps) {
  const t = useTranslations("Login");
  const [showPassword] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginFormSchema),
    defaultValues: {
      email: "",
      password: "",
    },
  });

  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <CardTitle>{t("title")}</CardTitle>
        <CardDescription>{t("description")}</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)}>
          <FieldGroup>
            <Field>
              <FieldContent>
                <FieldTitle>{t("emailLabel")}</FieldTitle>
                <Input
                  type="email"
                  placeholder={t("emailPlaceholder")}
                  {...register("email")}
                  disabled={isLoading}
                />
                <FieldError errors={errors.email ? [errors.email] : []} />
              </FieldContent>
            </Field>

            <Field>
              <FieldContent>
                <FieldTitle>{t("passwordLabel")}</FieldTitle>
                <Input
                  type={showPassword ? "text" : "password"}
                  placeholder="********"
                  {...register("password")}
                  disabled={isLoading}
                />
                <FieldError errors={errors.password ? [errors.password] : []} />
              </FieldContent>
            </Field>

            {error && (
              <div className="text-destructive text-sm" role="alert">
                {error}
              </div>
            )}

            <ActionButton type="submit" className="w-full" loading={isLoading}>
              {isLoading ? t("submitting") : t("submit")}
            </ActionButton>
          </FieldGroup>
        </form>
      </CardContent>
      <CardFooter className="flex flex-col gap-2">
        <Button
          type="button"
          variant="link"
          size="sm"
          className="h-auto p-0 text-muted-foreground hover:text-primary"
          onClick={() => {
            // TODO: Implement password recovery for the legacy AuthForm entry.
          }}
        >
          {t("forgotPassword")}
        </Button>
      </CardFooter>
    </Card>
  );
}
