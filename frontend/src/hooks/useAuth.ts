import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"

import {
  type Body_login_access_token as AccessToken,
  LoginService,
} from "@/client"

export const useAuth = () => {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  // Login xatosi login sahifasida inline ko'rsatiladi (toast emas).
  const loginMutation = useMutation({
    mutationFn: (data: AccessToken) =>
      LoginService.loginAccessToken({ formData: data }),
    onSuccess: () => {
      navigate({ to: "/" })
    },
  })

  const logoutMutation = useMutation({
    mutationFn: () => LoginService.logout(),
    onSettled: () => {
      queryClient.clear()
      navigate({ to: "/login" })
    },
  })

  const logout = () => logoutMutation.mutate()

  return {
    loginMutation,
    logout,
  }
}
