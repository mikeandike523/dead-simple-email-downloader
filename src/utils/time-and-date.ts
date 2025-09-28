export function sqlUtcTimestampToDate(timestamp: string): Date {
  return new Date(timestamp.replace(" ", "T") + "Z");
}

export function dateToSqlUtcTimestamp(date: Date): string {
    const pad = (n: number) => n.toString().padStart(2, "0");

  const year = date.getUTCFullYear();
  const month = pad(date.getUTCMonth() + 1); // months are 0-based
  const day = pad(date.getUTCDate());
  const hours = pad(date.getUTCHours());
  const minutes = pad(date.getUTCMinutes());
  const seconds = pad(date.getUTCSeconds());

  // Standard SQL DATETIME format
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
}