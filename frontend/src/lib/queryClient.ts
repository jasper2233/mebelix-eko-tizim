import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query"
import { AxiosError } from "axios"

/** Fallback: interceptor'dan keyin ham 401 chiqsa (masalan boshqa tabda logout
 * qilinib `token_version` mos kelmay qolsa) — keshni tozalab login'ga. */
const handleApiError = (error: Error) => {
  if (error instanceof AxiosError) {
    if (
      error.response?.status === 401 &&
      !error.config?.url?.includes("/login/access-token") &&
      window.location.pathname !== "/login"
    ) {
      queryClient.clear()
      window.location.href = "/login"
    }
  }
}

/** Modul darajasidagi yagona nusxa — komponentlar uni `useQueryClient()` bilan
 * provider'dan oladi, lekin `lib/guards.ts` React'dan TASHQARIDA (router
 * `beforeLoad`) ishlaydi va shu importga muhtoj. `main.tsx` dan import qilib
 * bo'lmaydi: main -> routeTree -> routes -> guards -> main aylanma bo'lardi. */
export const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: handleApiError }),
  mutationCache: new MutationCache({ onError: handleApiError }),
})
