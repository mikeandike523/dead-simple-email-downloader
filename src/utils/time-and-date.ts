export function sqlUtcTimestampToDate(timestamp: string): Date {
  return new Date(timestamp.replace(" ", "T") + "Z");
}