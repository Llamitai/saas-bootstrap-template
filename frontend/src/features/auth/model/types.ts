import { z } from "zod";

import { TenantRoleStatus, TenantStatus } from "@/entities/tenant";

export const rawEmailAddressSchema = z.object({
  email: z.email(),
  isVerified: z.boolean(),
});

export const rawPhoneNumberSchema = z.object({
  dialCode: z.number(),
  phoneNumber: z.string(),
  isoCode: z.string(),
  prefix: z.string().nullable().optional(),
});

export const userSchema = z.object({
  uuid: z.string(),
  username: z.string(),
  firstName: z.string().nullable().optional(),
  lastName: z.string().nullable().optional(),
  phoneNumber: rawPhoneNumberSchema.nullable().optional(),
  emailAddress: rawEmailAddressSchema.nullable().optional(),
  photoUrl: z.string().nullable().optional(),
  isSuperuser: z.boolean().optional(),
});

export const tenantSchema = z.object({
  uuid: z.string(),
  name: z.string(),
  slug: z.string(),
  timeZone: z.string(),
  countryCode: z.string(),
  currencyCode: z.string(),
  currencySymbol: z.string(),
  logoUrl: z.string().nullable().optional(),
  status: z.enum(TenantStatus),
  createdAt: z.string().nullable().optional(),
  updatedAt: z.string().nullable().optional(),
});

export const tenantRoleSchema = z.object({
  uuid: z.string(),
  tenantId: z.string(),
  name: z.string(),
  status: z.enum(TenantRoleStatus),
  permissions: z.array(z.record(z.string(), z.unknown())),
  iconUrl: z.string().nullable().optional(),
  isOwner: z.boolean().optional(),
});

export const jwtSessionSchema = z.object({
  accessToken: z.string(),
  refreshToken: z.string(),
  expiresIn: z.number().nullable().optional(),
  tokenType: z.string().nullable().optional(),
});

export const tenantUserSessionSchema = z.object({
  session: jwtSessionSchema,
  user: userSchema,
  tenant: tenantSchema.nullable(),
  tenantRole: tenantRoleSchema.nullable(),
});

export const tenantUserContextSchema = z.object({
  user: userSchema,
  tenant: tenantSchema.nullable(),
  tenantRole: tenantRoleSchema.nullable(),
});

export const loginFormSchema = z.object({
  email: z.email({ error: "Email invalido" }),
  password: z
    .string()
    .min(6, { error: "La contrasena debe tener al menos 6 caracteres" }),
});

export type LoginFormData = z.infer<typeof loginFormSchema>;

export interface LoginPayload {
  email: string;
  password: string;
}

export interface AcceptInvitationPayload {
  firstName: string;
  lastName: string | null;
  password?: string;
}
