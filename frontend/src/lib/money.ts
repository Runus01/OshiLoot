import type { FxRates, Money } from "../types";

/** Convert using ECB reference rates (all relative to EUR). Null when a rate is missing. */
export function convert(money: Money, to: string, fx: FxRates | null): number | null {
  if (money.currency === to) return money.amount;
  const from = fx?.rates[money.currency];
  const target = fx?.rates[to];
  if (!from || !target) return null;
  return (money.amount / from) * target;
}

export function formatMoney(amount: number, currency: string, locale?: string): string {
  try {
    return new Intl.NumberFormat(locale, { style: "currency", currency }).format(amount);
  } catch {
    return `${amount.toFixed(2)} ${currency}`;
  }
}

/** "¥4,800" or "¥4,800 (≈ S$42.10)" when the user's currency differs. */
export function describePrice(
  money: Money,
  userCurrency: string,
  fx: FxRates | null,
  locale?: string,
): { original: string; converted: string | null } {
  const original = formatMoney(money.amount, money.currency, locale);
  if (money.currency === userCurrency) return { original, converted: null };
  const amount = convert(money, userCurrency, fx);
  return {
    original,
    converted: amount === null ? null : `≈ ${formatMoney(amount, userCurrency, locale)}`,
  };
}
