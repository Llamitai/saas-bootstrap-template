export interface AuthHeaderContext {
  tenantSlug: string | null;
  accessToken: string | null;
  clearSession: () => void;
  setAccessToken: (accessToken: string) => void;
}

let readAuthHeaderContext = (): AuthHeaderContext => ({
  tenantSlug: null,
  accessToken: null,
  clearSession: () => undefined,
  setAccessToken: () => undefined,
});

export function configureAuthHeaderContext(
  reader: () => AuthHeaderContext
): void {
  readAuthHeaderContext = reader;
}

export function getAuthHeaderContext(): AuthHeaderContext {
  return readAuthHeaderContext();
}
