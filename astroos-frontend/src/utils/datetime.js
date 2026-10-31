function pad(value) {
  return String(value).padStart(2, "0");
}

export function toDateTimeLocalValue(date) {
  const source = date instanceof Date ? date : new Date(date);
  if (Number.isNaN(source.getTime())) return "";

  return `${source.getFullYear()}-${pad(source.getMonth() + 1)}-${pad(source.getDate())}T${pad(source.getHours())}:${pad(source.getMinutes())}`;
}

export function localInputToIso(value) {
  if (!value) return null;

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;

  const offsetMinutes = -date.getTimezoneOffset();
  const sign = offsetMinutes >= 0 ? "+" : "-";
  const absolute = Math.abs(offsetMinutes);
  const hours = pad(Math.floor(absolute / 60));
  const minutes = pad(absolute % 60);

  return `${value}:00${sign}${hours}:${minutes}`;
}

export function formatDateTime(value) {
  if (!value) return "Not specified";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Invalid date";

  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function formatClock(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";

  return new Intl.DateTimeFormat("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function minutesBetween(start, end) {
  const a = new Date(start);
  const b = new Date(end);
  if (Number.isNaN(a.getTime()) || Number.isNaN(b.getTime())) return null;
  return Math.max(0, Math.round((b.getTime() - a.getTime()) / 60000));
}
