import { queryOptions } from "@tanstack/react-query"

import { type UserRead, UsersService } from "@/client"
import { PAGE_SIZE } from "./mes"

export const getUsersQueryOptions = () =>
  queryOptions({
    queryKey: ["users"],
    // ponytail: hamma sahifalarni yig'ib olamiz — jadval client-side. Foydalanuvchilar
    // minglab bo'lsa, server-side paginatsiyaga (skip/limit + pageCount) o'tish kerak.
    queryFn: async () => {
      const first = await UsersService.readUsers({ skip: 0, limit: PAGE_SIZE })
      const data = [...first.data]
      while (data.length < first.count) {
        const page = await UsersService.readUsers({
          skip: data.length,
          limit: PAGE_SIZE,
        })
        if (page.data.length === 0) break
        data.push(...page.data)
      }
      return { data, count: first.count }
    },
  })

export const getCurrentUserQueryOptions = () =>
  queryOptions({
    // Tip aniq `UserRead | null`: useCurrentUser 401 da null bilan ishlaydi —
    // teglangan queryKey (queryOptions) o'sha kengroq tip bilan mos kelsin
    queryKey: ["currentUser"],
    queryFn: (): Promise<UserRead | null> => UsersService.readUserMe(),
  })
