import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query"
import { AxiosError } from "axios"

/** Fallback: interceptor'dan keyin ham 401 chiqsa (masalan boshqa tabda logout
 * qilinib `token_version` mos kelmay qolsa) — keshni tozalab login'ga. */
const handleApiError = (error: Error) => {
  if (error instanceof AxiosError) {
    if (
      error.response?.status === 401 &&
      // FAQAT `/login/access-token` chetlab o'tiladi — u yerdagi 401 "parol
      // xato" degani. `/login/refresh` va `/login/badge` ATAYLAB ro'yxatda YO'Q.
      // (main.tsx dagi interceptor butun `/login/*` ni chetlab o'tadi, lekin
      // uning vazifasi boshqa — yiqilgan refresh'ni qayta refresh qilmaslik.)
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
  defaultOptions: {
    queries: {
      // TanStack default `retry: 3` — tsex Wi-Fi uzilganda har xato ~7 s jim
      // turadi (3 ta qayta urinish + backoff), keyingina `isError` yonadi.
      // Bitta qayta urinish tarmoqning bir martalik uzilishiga yetadi.
      retry: 1,
      // Tablo/terminal ekranlari o'z `refetchInterval` i bilan yangilanadi;
      // qolgan sahifalar uchun har alt-tab'da qayta so'rash ortiqcha yuk.
      refetchOnWindowFocus: false,
      // Global `staleTime` ATAYLAB berilmagan: u bir joydan hamma sahifa
      // xulqini o'zgartiradi, mutatsiyadan keyingi yangilanish esa
      // `invalidateQueries` ga tayanadi. Kerak bo'lgan joyda so'rovning
      // o'zida beriladi (`queries/`, `routes/`).
    },
  },
})
