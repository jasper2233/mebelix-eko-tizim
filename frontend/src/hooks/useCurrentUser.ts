import { useQuery } from "@tanstack/react-query"
import { getCurrentUserQueryOptions } from "@/queries/users"

export const useCurrentUser = () => {
  // Tip queryOptions'dan keladi — qo'lda generik kerak emas. So'rov hali
  // tugamagan bo'lsa `undefined` (guard'lar uni allaqachon keshga solgan).
  const { data: currentUser } = useQuery(getCurrentUserQueryOptions())

  return { currentUser }
}
