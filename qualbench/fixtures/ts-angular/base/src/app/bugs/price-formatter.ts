/**
 * Formats a price in cents (integer) as a currency string, e.g.
 * formatPrice(1050) -> "$10.50", formatPrice(5) -> "$0.05".
 */
export function formatPrice(cents: number): string {
  // BUG: divides by 100 but does not pad single-digit cent remainders,
  // so formatPrice(5) produces "$0.5" instead of "$0.05", and
  // formatPrice(1050) produces "$10.5" instead of "$10.50" (trailing
  // zero on exact ten-cent amounts is also dropped).
  const dollars = Math.floor(cents / 100);
  const remainder = cents % 100;
  return `$${dollars}.${remainder}`;
}
