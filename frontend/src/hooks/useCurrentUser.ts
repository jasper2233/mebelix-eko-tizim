import { useQuery } from "@tanstack/react-query"
import type { UserRead } from "@/client"
import { getCurrentUserQueryOptions } from "@/queries/users"

const useCurrentUser = () => {
  const { data: currentUser } = useQuery<UserRead | null, Error>({
    ...getCurrentUserQueryOptions(),
    retry: false,
  })

  return { currentUser }
}

export default useCurrentUser
