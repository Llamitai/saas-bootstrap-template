"use client";

import { isAxiosError } from "axios";
import { useTranslations } from "next-intl";
import { useCallback } from "react";
import { handleHttpError, normalizeErrorFeedback } from "@/shared/http/errors";

/** Catalog keys cannot contain dots: `bff.upstream_error` -> `bff_upstream_error`. */
export function httpErrorCatalogKey(code: string): string {
  return code.replaceAll(".", "_");
}

/**
 * Turns a failed request into user-facing text: a translated `HttpErrors`
 * entry for known codes, otherwise the backend's own message, otherwise the
 * caller's translated fallback.
 */
export function useHttpErrorMessage() {
  const t = useTranslations("HttpErrors");

  return useCallback(
    (error: unknown, fallback: string): string => {
      if (!isAxiosError(error)) return fallback;
      const item = handleHttpError(error).errors[0];
      if (!item) return fallback;

      const key = httpErrorCatalogKey(item.code);
      if (t.has(key)) return t(key);
      if (normalizeErrorFeedback(error.response?.data)) return item.message;
      return fallback;
    },
    [t]
  );
}
