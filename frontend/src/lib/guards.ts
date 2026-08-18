import { redirect } from "@tanstack/react-router"
import { AxiosError } from "axios"

import { type UserRead, UsersService } from "@/client"

/**
 * Autentifikatsiya guard'i (`beforeLoad`): 401 — login sahifasiga.
 *
 * Faqat 401 login'ga yo'naltiradi — tarmoq uzilishi/5xx da sessiyani
 * o'ldirmaymiz, xato errorComponent'da ko'rinadi. Foydalanuvchini qaytaradi:
 * rolga qarab qo'shimcha yo'naltirish (terminal/tablo) chaqiruvchining ishi.
 */
export async function requireAuth(): Promise<UserRead> {
  try {
    return (await UsersService.readUserMe()).data
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
    const { data: me } = await UsersService.readUserMe()
    if (!allow(me)) throw redirect({ to: "/" })
  }
