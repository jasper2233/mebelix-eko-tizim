import { z } from "zod"

import { groupThousands } from "@/lib/mes"

// Mirror the limits enforced by the backend (see `backend/app/schemas/users.py`).
// Keep these in sync when tightening or relaxing rules on either side.
const PASSWORD_MIN_LENGTH = 8
const NAME_MAX_LENGTH = 100

// E.164 Uzbek mobile: `+998` + 9 digits, no spaces. Matches `PHONE_PATTERN` on the server.
export const PHONE_PATTERN = /^\+998\d{9}$/
const PHONE_INVALID = "Telefon +998XXXXXXXXX formatida bo'lishi kerak"

const PASSWORD_TOO_SHORT = `Parol kamida ${PASSWORD_MIN_LENGTH} ta belgidan iborat bo'lishi kerak`

/** Required password field (sign-up / new password). Mirrors `validate_password_strength` on the server. */
export const passwordSchema = z
  .string()
  .min(1, { message: "Parol majburiy" })
  .min(PASSWORD_MIN_LENGTH, { message: PASSWORD_TOO_SHORT })
  .regex(/[a-z]/, {
    message: "Parolda kamida bitta kichik harf bo'lishi kerak",
  })
  .regex(/[A-Z]/, { message: "Parolda kamida bitta katta harf bo'lishi kerak" })
  .regex(/\d/, { message: "Parolda kamida bitta raqam bo'lishi kerak" })
  .regex(/[^a-zA-Z0-9]/, {
    message: "Parolda kamida bitta maxsus belgi bo'lishi kerak",
  })

/** Ko'rinishda "+998 90 123-45-67", submit'da kanonik "+998901234567" (transform). */
export const optionalFormattedPhoneSchema = z
  .string()
  .transform((v) => v.replace(/[\s-]+/g, ""))
  .refine((v) => v === "" || PHONE_PATTERN.test(v), { message: PHONE_INVALID })

/** O'shaning MAJBURIY varianti — login identifikatori (user) va shunga o'xshash
 *  maydonlar uchun: bo'sh qoldirib bo'lmaydi. */
export const formattedPhoneSchema = optionalFormattedPhoneSchema.refine(
  (v) => v !== "",
  { message: "Telefon majburiy" },
)

/** Ko'rinishdagi "+998" prefiksini tashlab, faqat abonent raqamining 9 ta raqamini qaytaradi. */
function phoneDigits(s: string): string {
  let t = s.trim()
  if (t.startsWith("+998"))
    t = t.slice(4) // display/paste prefiksi raqam emas
  else if (t.startsWith("+")) t = t.slice(1)
  let d = t.replace(/\D/g, "")
  if (d.length > 9 && d.startsWith("998")) d = d.slice(3) // davlat kodi plyussiz terilgan
  return d.slice(0, 9)
}

/** API'dan kelgan Decimal-satrni ("14000000.00") input qiymatiga tayyorlaydi
 * (`null` → ""). Kasr qoidasi `formatMoneyInput` da. */
export function moneyToInput(value: string | null | undefined): string {
  return formatMoneyInput(String(value ?? ""))
}

/** Pul maydoni avto-separatori: "5000000" → "5 000 000" (max 12 raqam);
 * submit'da bo'shliqlar olib tashlanadi. Guruhlash qoidasi ko'rsatish bilan
 * BITTA (`groupThousands`).
 *
 * So'm — BUTUN son (tiyin yo'q), shuning uchun birinchi `.` yoki `,` SONNING
 * TUGASHI: undan keyingisi tashlanadi. Ilgari faqat raqamlar qoldirilardi va
 * kasr nollari summaga yopishardi: "1500000.0" → "15 000 000" (ortiqcha nol),
 * Excel/1C'dan qo'yilgan "5 000 000,00" → ×100; tahrirlashda API'ning
 * "14000000.00" i ×100 (afad9f6 da faqat o'sha yo'l yamalgan edi). Vergul
 * pulda minglik ajratgich sifatida hech qayerda ishlatilmaydi (ko'rsatish
 * ham bo'shliq bilan) — demak u faqat kasr, taxmin yo'q. */
export function formatMoneyInput(input: string): string {
  const d = input
    .replace(/[.,][\s\S]*$/, "")
    .replace(/\D/g, "")
    .replace(/^0+(?=\d)/, "")
    .slice(0, 12)
  return groupThousands(d)
}

/**
 * Yozish paytida avto-separator, o'zbek standarti: "+998 90 123-45-67".
 * `prev` bilan: separator o'chirilganda oxirgi raqam ham ketadi (backspace qulfini oldini oladi).
 */
export function formatUzPhone(input: string, prev = ""): string {
  let d = phoneDigits(input)
  if (input.length < prev.length && d === phoneDigits(prev)) d = d.slice(0, -1)
  if (!d) return ""
  let out = `+998 ${d.slice(0, 2)}`
  if (d.length > 2) out += ` ${d.slice(2, 5)}`
  if (d.length > 5) out += `-${d.slice(5, 7)}`
  if (d.length > 7) out += `-${d.slice(7, 9)}`
  return out
}

/** Optional name: empty input becomes `undefined` (the backend rejects "" with min_length=2). */
export const optionalNameSchema = z
  .string()
  .trim()
  .max(NAME_MAX_LENGTH, {
    message: `Ism ko'pi bilan ${NAME_MAX_LENGTH} ta belgi bo'lishi mumkin`,
  })
  .refine((v) => v === "" || v.length >= 2, {
    message: "Ism kamida 2 ta belgidan iborat bo'lishi kerak",
  })
  .transform((v) => (v === "" ? undefined : v))
  .optional()
