import { UsersService } from "@/client"

export function getUsersQueryOptions() {
  return {
    queryFn: () => UsersService.readUsers({ skip: 0, limit: 100 }),
    queryKey: ["users"] as const,
  }
}

export function getCurrentUserQueryOptions() {
  return {
    queryFn: UsersService.readUserMe,
    queryKey: ["currentUser"] as const,
  }
}
