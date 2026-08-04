import { redirect } from "@tanstack/react-router"

import { type UserRead, UsersService } from "@/client"

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
    const me = await UsersService.readUserMe()
    if (!allow(me)) throw redirect({ to: "/" })
  }
