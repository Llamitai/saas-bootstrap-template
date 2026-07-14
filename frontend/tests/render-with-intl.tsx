import {
  type RenderOptions,
  render as rtlRender,
} from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactElement, ReactNode } from "react";

import messages from "@/src/i18n/messages/en.json";

// Test render helper that mounts NextIntlClientProvider so components calling
// `useTranslations` work under vitest. Locale is pinned to "en": the run-summary
// components mix i18n strings with English labels from verdict-config.ts, and the
// unit tests assert that English copy. Re-exports the full @testing-library/react
// surface and overrides `render` via the `wrapper` option.
function IntlWrapper({ children }: { children: ReactNode }) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

export function renderWithIntl(
  ui: ReactElement,
  options?: Omit<RenderOptions, "wrapper">
) {
  return rtlRender(ui, { wrapper: IntlWrapper, ...options });
}

export * from "@testing-library/react";
export { renderWithIntl as render };
