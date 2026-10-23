import type { Charge } from "../types/contracts";

const amountFormatter = new Intl.NumberFormat("zh-CN", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 20,
});

/** Display only: reuse an equal plain-decimal source value without parsing locales. */
export function formatChargeAmount(charge?: Charge): string {
  const value = charge?.charge_details?.amount;
  if (value == null) return "—";
  const raw = charge?.raw_amount?.trim();
  if (raw && /^[+-]?\d+(?:\.\d+)?$/.test(raw) && Number(raw) === value)
    return raw;
  return amountFormatter.format(value);
}
