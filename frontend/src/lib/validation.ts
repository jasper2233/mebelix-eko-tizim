import { z } from "zod"

// Mirror the limits enforced by the backend (see `backend/app/schemas/users.py`).
// Keep these in sync when tightening or relaxing rules on either side.
export const PASSWORD_MIN_LENGTH = 8
export const NAME_MAX_LENGTH = 30

// E.164 Uzbek mobile: `+998` + 9 digits, no spaces. Matches `PHONE_PATTERN` on the server.
export const PHONE_PATTERN = /^\+998\d{9}$/
const PHONE_INVALID = "Telefon +998XXXXXXXXX formatida bo'lishi kerak"

const PASSWORD_TOO_SHORT = `Parol kamida ${PASSWORD_MIN_LENGTH} ta belgidan iborat bo'lishi kerak`

/** Required password field (sign-up / new password). */
export const passwordSchema = z
  .string()
  .min(1, { message: "Parol majburiy" })
  .min(PASSWORD_MIN_LENGTH, { message: PASSWORD_TOO_SHORT })

/** Optional password field (admin edit form: empty = "don't change"). */
export const optionalPasswordSchema = z
  .string()
  .min(PASSWORD_MIN_LENGTH, { message: PASSWORD_TOO_SHORT })
  .optional()
  .or(z.literal(""))

export const phoneSchema = z
  .string()
  .min(1, { message: "Telefon majburiy" })
  .regex(PHONE_PATTERN, { message: PHONE_INVALID })

export const optionalNameSchema = z.string().max(NAME_MAX_LENGTH).optional()
