export function formatDistance(value: number | null): string {
  if (value === null) return "N/A";
  if (value < 1000) return `${Math.round(value)} m`;
  return `${(value / 1000).toFixed(2)} km`;
}

export function formatSpeed(value: number | null): string {
  return value === null ? "N/A" : `${value.toFixed(1)} km/h`;
}

export function formatDuration(value: number | null): string {
  if (value === null) return "N/A";
  const minutes = Math.floor(value / 60);
  const seconds = Math.floor(value % 60);
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

export function formatRating(value: number | null): string {
  return value === null ? "N/A" : value.toFixed(1);
}

export function formatCount(value: number | null): string {
  return value === null ? "N/A" : value.toLocaleString();
}

export function formatTimestamp(timestampMs: number): string {
  return formatDuration(Math.floor(timestampMs / 1000));
}

export function formatMatchDate(value: string): string {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
  }).format(new Date(value));
}
