import { useQuery } from "@tanstack/react-query"
import { getCurrentUserQueryOptions } from "@/queries/users"

export const useCurrentUser = () => {
  // Tip (UserRead | null) queryOptions'dan keladi — qo'lda generik kerak emas
  const { data: currentUser } = useQuery({
    ...getCurrentUserQueryOptions(),
    retry: false,
  })

  return { currentUser }
}
