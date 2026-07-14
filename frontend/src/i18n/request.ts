import { cookies } from "next/headers";
import { getRequestConfig } from "next-intl/server";

import { defaultLocale, isLocale, LOCALE_COOKIE } from "@/src/i18n/config";

export default getRequestConfig(async () => {
  const store = await cookies();
  const cookieValue = store.get(LOCALE_COOKIE)?.value;
  const locale = isLocale(cookieValue) ? cookieValue : defaultLocale;

  const messages = (await import(`@/src/i18n/messages/${locale}.json`)).default;

  return {
    locale,
    messages,
  };
});
