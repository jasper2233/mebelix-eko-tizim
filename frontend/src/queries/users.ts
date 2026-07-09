import { UsersService } from "@/client"

const PAGE_SIZE = 100 // backend MAX_PAGE_SIZE

export function getUsersQueryOptions() {
  return {
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
    queryKey: ["users"] as const,
  }
}

export function getCurrentUserQueryOptions() {
  return {
    queryFn: UsersService.readUserMe,
    queryKey: ["currentUser"] as const,
  }
}
