export const MONTHS_ES = [
  "enero",
  "febrero",
  "marzo",
  "abril",
  "mayo",
  "junio",
  "julio",
  "agosto",
  "septiembre",
  "octubre",
  "noviembre",
  "diciembre",
] as const;

const MONTHS_SHORT_ES = [
  "Ene",
  "Feb",
  "Mar",
  "Abr",
  "May",
  "Jun",
  "Jul",
  "Ago",
  "Sep",
  "Oct",
  "Nov",
  "Dic",
] as const;

const MONTHS_SHORT_EN = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
] as const;

export const DAY_HEADERS_ES = [
  "lu",
  "ma",
  "mi",
  "ju",
  "vi",
  "sá",
  "do",
] as const;

export function parseLocalDate(value: string): Date | null {
  if (!value) return null;
  const [year, month, day] = value.split("-").map(Number);
  if (!year || !month || !day) return null;
  return new Date(year, month - 1, day);
}

export function toDateStr(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

export function formatShortDate(iso: string, locale = "es"): string {
  const date = parseLocalDate(iso);
  if (!date) return "";
  const months = locale === "es" ? MONTHS_SHORT_ES : MONTHS_SHORT_EN;
  return `${date.getDate()}/${months[date.getMonth()]}/${date.getFullYear()}`;
}

export function formatDateRangeLabel(
  from: string,
  to: string,
  locale = "es",
  placeholder = "Rango de fechas"
): string {
  if (from && to) {
    return `${formatShortDate(from, locale)} – ${formatShortDate(to, locale)}`;
  }
  if (from) return `desde ${formatShortDate(from, locale)}`;
  if (to) return `hasta ${formatShortDate(to, locale)}`;
  return placeholder;
}

export function daysInMonth(year: number, month: number): number {
  return new Date(year, month + 1, 0).getDate();
}

export function firstDayOffset(year: number, month: number): number {
  return (new Date(year, month, 1).getDay() + 6) % 7;
}

export function shiftMonth(
  year: number,
  month: number,
  delta: number
): [number, number] {
  const date = new Date(year, month + delta, 1);
  return [date.getFullYear(), date.getMonth()];
}
