import {
  MutationCache,
  QueryCache,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query"
import { createRouter, RouterProvider } from "@tanstack/react-router"
import axios from "axios"
import { StrictMode } from "react"
import ReactDOM from "react-dom/client"
import { ApiError, LoginService, OpenAPI } from "./client"
import "./index.css"
import { routeTree } from "./routeTree.gen"

// Cookies are sent automatically via withCredentials — no token in JS memory.
OpenAPI.BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000"
OpenAPI.WITH_CREDENTIALS = true
axios.defaults.timeout = Number(import.meta.env.VITE_API_TIMEOUT_MS ?? 30_000)

// --- Silent refresh: bir vaqtda kelgan 401'lar bitta promise'ni kutadi ---

let refreshing: Promise<unknown> | null = null

axios.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config
    // `/login/*` chetlab o'tiladi: u yerdagi 401 "sessiya eskirdi" emas, "kirish
    // ma'lumoti noto'g'ri" degani. Refresh urinilsa, uning o'z xatosi asl
    // xabarni bosib qolardi — beyjik skanerlagan operator "Beyjik topilmadi"
    // o'rniga "Yangilash tokeni topilmadi" ni ko'rardi.
    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes("/login/")
    ) {
      originalRequest._retry = true
      // Server sets the new access_token cookie in the response automatically.
      refreshing ??= LoginService.refreshAccessToken().finally(() => {
        refreshing = null
      })
      await refreshing // refresh yiqilsa — kutayotgan barcha so'rov shu xato bilan rad etiladi
      return axios(originalRequest)
    }
    return Promise.reject(error)
  },
)

// Fallback: if a query/mutation still surfaces a 401 after the interceptor
// (e.g. token_version mismatch after logout on another tab), redirect to login.
const handleApiError = (error: Error) => {
  if (error instanceof ApiError) {
    if (
      error.status === 401 &&
      !error.url.includes("/login/access-token") &&
      window.location.pathname !== "/login"
    ) {
      queryClient.clear()
      window.location.href = "/login"
    }
  }
}

const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: handleApiError,
  }),
  mutationCache: new MutationCache({
    onError: handleApiError,
  }),
})

const router = createRouter({ routeTree })
declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router
  }
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
)
