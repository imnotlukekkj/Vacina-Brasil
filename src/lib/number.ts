export function parsePtNumber(v: unknown): number | null {
  if (v === null || v === undefined) return null;
  if (typeof v === "number") {
    return Number.isFinite(v) ? v : null;
  }
  if (typeof v !== "string") {
    // try native coercion for non-string values
    const n = Number(v as number | string | bigint | boolean);
    return Number.isFinite(n) ? n : null;
  }

  let s = (v as string).trim();
  if (s === "") return null;
  // remove non-breaking spaces
  s = s.replace(/\u00A0/g, "");

  // If contains both dot and comma, assume dot is thousands separator and comma decimal
  if (s.indexOf('.') !== -1 && s.indexOf(',') !== -1) {
    s = s.replace(/\./g, '').replace(/,/g, '.');
  } else {
    // If only dots and more than one, remove dots (thousands separators)
    const dotCount = (s.match(/\./g) || []).length;
    const commaCount = (s.match(/,/g) || []).length;
    if (dotCount > 1 && commaCount === 0) {
      s = s.replace(/\./g, '');
    }
    // If single comma, treat as decimal separator
    if (commaCount === 1 && dotCount === 0) {
      s = s.replace(/,/g, '.');
    }
  }

  // strip any remaining non-digit/decimal/minus chars
  s = s.replace(/[^0-9.-]/g, '');
  if (s === '' || s === '.' || s === '-' || s === '-.' ) return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

export default parsePtNumber;
