/* The time of day comes from the server. A kiosk on the venue network often has no time
   source of its own, and a screen that is ten minutes off counts down to the wrong moment.
   Every bundle carries the server's time; the difference to this device's clock is kept
   and applied wherever the display shows or compares a time. */

let offsetMs = 0;

/** Note the server's time, as received just now. */
export function syncClock(serverNow: string, receivedAt: number = Date.now()): void {
  const server = Date.parse(serverNow);
  if (Number.isFinite(server)) offsetMs = server - receivedAt;
}

/** The current time by the server's clock, in milliseconds. */
export function serverNow(): number {
  return Date.now() + offsetMs;
}
