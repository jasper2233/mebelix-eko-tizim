import { redirect } from "@tanstack/react-router"
import { AxiosError } from "axios"

import type { UserRead } from "@/client"
import { queryClient } from "@/lib/queryClient"
import { getCurrentUserQueryOptions } from "@/queries/users"

/** Joriy foydalanuvchi — KESHDAN.
 *
 * `beforeLoad` React'dan tashqarida ishlaydi, ya'ni `useQuery` yo'q; lekin
 * `ensureQueryData` o'sha keshning o'zidan o'qiydi. Ilgari bu yerda
 * `UsersService.readUserMe()` to'g'ridan-to'g'ri chaqirilardi — kesh chetlab
 * o'tilib, HAR navigatsiya ikkita ketma-ket `/users/me` ni kutardi
 * (`_layout` guard'i + sahifa guard'i), Frankfurt RTT'da ~218 ms.
 * Endi birinchi so'rovdan keyin navigatsiya tarmoqni umuman kutmaydi. */
const me = () => queryClient.ensureQueryData(getCurrentUserQueryOptions())

/**
 * Autentifikatsiya guard'i (`beforeLoad`): 401 — login sahifasiga.
 *
 * Faqat 401 login'ga yo'naltiradi — tarmoq uzilishi/5xx da sessiyani
 * o'ldirmaymiz, xato errorComponent'da ko'rinadi. Foydalanuvchini qaytaradi:
 * rolga qarab qo'shimcha yo'naltirish (terminal/tablo) chaqiruvchining ishi.
 */
export async function requireAuth(): Promise<UserRead> {
  try {
    return await me()
  } catch (err) {
    if (err instanceof AxiosError && err.response?.status === 401) {
      throw redirect({ to: "/login" })
    }
    throw err
  }
}

/**
 * Route guard: huquq yetmasa bosh sahifaga qaytaradi.
 *
 * `beforeLoad` da ishlaydi — sahifaning so'rovlari umuman yuborilmaydi.
 * Render ichida tekshirish kech: brauzer ma'lumotni yuklab, keshga solib
 * bo'lgandan keyin "ruxsat yo'q" ekrani chiqadi.
 *
 * Ruxsat predikati `lib/mes` dan olinadi — sidebar ham aynan shularni ishlatadi.
 */
export const requireAccess =
  (allow: (user: UserRead) => boolean) => async () => {
    if (!allow(await me())) throw redirect({ to: "/" })
  }
