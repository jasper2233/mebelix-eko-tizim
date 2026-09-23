/** Eshik ochilishining ORALIQ holatlari.
 *
 * Backend har harakatlanadigan panelning ikki holatini beradi: yopiq (`p`, `q`)
 * va ochiq (`po`, `qo`). Ilgari oraliq kadrlar ikkalasi orasida TO'G'RI chiziq
 * bo'ylab (lerp) va burilish slerp bilan alohida hisoblanardi — uchlari to'g'ri,
 * lekin 460 ms lik harakat o'rtasida eshik ilgagidan ko'chib, korpus ichidan
 * o'tardi (22 namunaning 315 eshigida median 85 mm, eng ko'pi 223 mm).
 *
 * Ilgakning o'qi ikki holatdan ANIQ tiklanadi, JSON'ga yangi maydon kerak emas:
 * `R = qo·q⁻¹` burilish (o'q `a`, burchak `θ`), o'q nuqtasi `c` esa
 * `(I − R)·c = po − R·p` tenglamasidan. Tortma (burilishsiz) avvalgidek
 * to'g'ri chiziq bo'ylab suriladi.
 *
 * Alohida modul, chunki faqat `three` ga bog'liq — `node` bilan to'g'ridan-to'g'ri
 * sinab ko'rsa bo'ladi.
 */

import { Quaternion, Vector3 } from "three"

export type Ilgak = {
  /** O'qdagi nuqta (dunyo koordinatasi) */
  c: Vector3
  /** To'liq ochilish burilishi `qo·q⁻¹` */
  dq: Quaternion
  /** Siljishning o'q bo'ylab qismi — sof ilgakda ~0, lekin uchlar aniq tushsin */
  dPar: Vector3
}

const BIR = new Quaternion()

/** Panel burilib ochiladimi — shunda uning o'qi; faqat siljisa `null`. */
export const ilgakOqi = (
  p: Vector3,
  q: Quaternion,
  po: Vector3,
  qo: Quaternion,
): Ilgak | null => {
  const dq = qo.clone().multiply(q.clone().invert()).normalize()
  if (dq.w < 0) dq.set(-dq.x, -dq.y, -dq.z, -dq.w)
  const teta = 2 * Math.acos(Math.min(1, dq.w))
  const s = Math.sqrt(Math.max(0, 1 - dq.w * dq.w))
  if (teta < 1e-4 || s < 1e-9) return null
  const a = new Vector3(dq.x / s, dq.y / s, dq.z / s)
  const d = po.clone().sub(p.clone().applyQuaternion(dq))
  const dPar = a.clone().multiplyScalar(d.dot(a))
  const y = d.clone().sub(dPar)
  // (I − R) o'qqa perpendikulyar tekislikda teskarilanadi:
  // c = ((1 − cosθ)·y + sinθ·(a × y)) / (2·(1 − cosθ))
  const cos = Math.cos(teta)
  const c = y
    .clone()
    .multiplyScalar(1 - cos)
    .add(a.clone().cross(y).multiplyScalar(Math.sin(teta)))
    .divideScalar(2 * (1 - cos))
  return { c, dq, dPar }
}

/** `k` (0..1) ochiqlikdagi joylashuv va burilish: `c` atrofida `k` ulush burilish. */
export const ilgakHolati = (
  il: Ilgak,
  p: Vector3,
  q: Quaternion,
  k: number,
  pos: Vector3,
  quat: Quaternion,
): void => {
  const rk = new Quaternion().slerpQuaternions(BIR, il.dq, k)
  pos
    .copy(p)
    .sub(il.c)
    .applyQuaternion(rk)
    .add(il.c)
    .addScaledVector(il.dPar, k)
  quat.copy(rk).multiply(q)
}
