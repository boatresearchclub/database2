/**
 * Conditional third rates are authored with Python round(100*n/N, 1).
 * Use round-half-to-even rather than JS Math.round for exact .05 ties.
 * This deliberately uses integer arithmetic and returns 1-decimal percent.
 */
export function officialKPercent(n,denominator){
  if(!Number.isSafeInteger(n)||!Number.isSafeInteger(denominator)
      ||n<0||denominator<1||n>denominator||!Number.isSafeInteger(1000*n))
    throw Error("INVALID_OFFICIAL_COUNT");
  const num=1000*n;
  const base=Math.floor(num/denominator);
  const remainder=num%denominator;
  const twice=2*remainder;
  const increment=twice>denominator||(twice===denominator&&base%2===1);
  return (base+(increment?1:0))/10;
}
