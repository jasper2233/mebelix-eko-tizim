import { QueryClientProvider } from "@tanstack/react-query"
import { createRouter, RouterProvider } from "@tanstack/react-router"
import { StrictMode } from "react"
import ReactDOM from "react-dom/client"
import { BrandLoader } from "@/components/Common/BrandLoader"
import { LoginService } from "./client"
import { client } from "./client/client.gen"
import "./index.css"
import { queryClient } from "./lib/queryClient"
import { routeTree } from "./routeTree.gen"
import { API_BASE } from "./utils"

// Cookies are sent automatically via withCredentials — no token in JS memory.
// Klient O'Z axios instansiyasini yaratadi (`client.instance`), shuning uchun
// sozlama ham, interceptor ham global `axios` ga emas, o'shanga qo'yiladi.
client.setConfig({
  baseURL: API_BASE,
  withCredentials: true,
  timeout: Number(import.meta.env.VITE_API_TIMEOUT_MS ?? 30_000),
})

// --- Silent refresh: bir vaqtda kelgan 401'lar bitta promise'ni kutadi ---

let refreshing: Promise<unknown> | null = null

client.instance.interceptors.response.use(
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
      return client.instance(originalRequest)
    }
    return Promise.reject(error)
  },
)

const router = createRouter({
  routeTree,
  // Route yuklanishi (beforeLoad auth so'rovi ham) 200ms dan cho'zilsa brend
  // loader chiqadi; minMs — bir soniya ko'rinib "lip" etib yo'qolmasin
  defaultPendingComponent: () => (
    <div className="flex min-h-screen items-center justify-center text-primary">
      <BrandLoader size={88} />
    </div>
  ),
  defaultPendingMs: 200,
  defaultPendingMinMs: 500,
})
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
