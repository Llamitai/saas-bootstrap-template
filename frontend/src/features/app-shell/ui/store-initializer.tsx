"use client";

import { useTenantsQuery } from "@/features/tenants";

export function StoreInitializer() {
  useTenantsQuery();

  return null;
}
