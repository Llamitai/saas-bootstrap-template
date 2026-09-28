import { AxiosError, AxiosHeaders } from "axios";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { useHttpErrorMessage } from "@/shared/hooks/use-http-error-message";
import messages from "@/src/i18n/messages/en.json";
import { renderHook } from "@/tests/render-with-intl";

function wrapper({ children }: { children: ReactNode }) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

function axiosError(status: number, data?: unknown): AxiosError {
  const config = { headers: new AxiosHeaders() };
  return new AxiosError("failed", "ERR", config, null, {
    status,
    statusText: "",
    headers: {},
    config,
    data,
  });
}

describe("useHttpErrorMessage", () => {
  const message = () =>
    renderHook(() => useHttpErrorMessage(), { wrapper }).result.current;

  it("translates status-derived codes", () => {
    expect(message()(axiosError(429), "fallback")).toBe(
      "Too many requests. Try again in a moment."
    );
  });

  it("translates BFF codes that contain dots", () => {
    const error = axiosError(502, {
      errors: [{ code: "bff.upstream_unreachable", message: "raw" }],
      validation: null,
    });
    expect(message()(error, "fallback")).toBe(
      "The service could not be reached. Try again."
    );
  });

  it("keeps the backend message for domain codes without a catalog entry", () => {
    const error = axiosError(409, {
      errors: [{ code: "tenant_user.invitation_pending", message: "Pending" }],
      validation: null,
    });
    expect(message()(error, "fallback")).toBe("Pending");
  });

  it("uses the caller fallback for non-HTTP failures", () => {
    expect(message()(new Error("boom"), "fallback")).toBe("fallback");
  });
});
