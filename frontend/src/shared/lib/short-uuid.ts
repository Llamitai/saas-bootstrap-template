export function shortUuid(uuid: string, length = 10): string {
  return uuid.replace(/-/g, "").slice(0, length);
}
