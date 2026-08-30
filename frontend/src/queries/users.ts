import { queryOptions } from "@tanstack/react-query"

import { type UserRead, UsersService } from "@/client"
import { PAGE_SIZE } from "./mes"

export const getUsersQueryOptions = () =>
  queryOptions({
    queryKey: ["users"],
    // ponytail: hamma sahifalarni yig'ib olamiz — jadval client-side. Foydalanuvchilar
    // minglab bo'lsa, server-side paginatsiyaga (skip/limit + pageCount) o'tish kerak.
    queryFn: async () => {
      const { data: first } = await UsersService.readUsers({
        query: { skip: 0, limit: PAGE_SIZE },
      })
      const data = [...first.data]
      while (data.length < first.count) {
        const { data: page } = await UsersService.readUsers({
          query: { skip: data.length, limit: PAGE_SIZE },
        })
        if (page.data.length === 0) break
        data.push(...page.data)
      }
      return { data, count: first.count }
    },
  })

export const getCurrentUserQueryOptions = () =>
  queryOptions({
    queryKey: ["currentUser"],
    queryFn: async (): Promise<UserRead> =>
      (await UsersService.readUserMe()).data,
    // `useCurrentUser` (AppSidebar, sahifalar) va `tablo.tsx` observer'larining
    // mount/fokus refetch'larini to'xtatadi — /users/me har sahifa o'tishida va
    // har oyna fokusida qaytadan so'ralmaydi. (Guard'lar `ensureQueryData` bilan
    // keshdan o'qiydi va staleTime'ga umuman qaramaydi — sabab `lib/guards.ts` da.)
    // Eskirgan rol xavf tug'dirmaydi: guard faqat UI yo'naltirgichi, huquqni
    // backend har so'rovda o'zi tekshiradi; parol/rol o'zgarsa 401 keladi va
    // `lib/queryClient.ts` dagi handler login'ga chiqaradi.
    staleTime: 5 * 60_000,
  })
