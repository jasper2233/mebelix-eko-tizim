import { z } from "zod"

// Mirror the limits enforced by the backend (see `backend/app/schemas/users.py`).
// Keep these in sync when tightening or relaxing rules on either side.
export const PASSWORD_MIN_LENGTH = 8
export const NAME_MAX_LENGTH = 30

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

/** Optional password field (admin edit form: empty = "don't change"). */
export const optionalPasswordSchema = passwordSchema
  .optional()
  .or(z.literal(""))

export const phoneSchema = z
  .string()
  .min(1, { message: "Telefon majburiy" })
  .regex(PHONE_PATTERN, { message: PHONE_INVALID })

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
