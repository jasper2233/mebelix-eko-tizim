import { type QueryClient, queryOptions } from "@tanstack/react-query"
import { toast } from "sonner"

import {
  BridgeAgentsService,
  ClientsService,
  EmployeesService,
  MachinesService,
  type OrderStatus,
  OrdersService,
  PostsService,
  TabloService,
  TerminalService,
} from "@/client"
import { handleError } from "@/utils"

// Small reference sets are fetched whole; registries pull up to the backend max page.
export const PAGE_SIZE = 100 // backend MAX_PAGE_SIZE

export const getPostsQueryOptions = () =>
  queryOptions({
    queryKey: ["posts"],
    queryFn: async () => (await PostsService.readPosts()).data,
    staleTime: 5 * 60_000,
  })

export const getMachinesQueryOptions = () =>
  queryOptions({
    queryKey: ["machines"],
    queryFn: async () => (await MachinesService.readMachines()).data,
    staleTime: 60_000,
  })

export const getClientsQueryOptions = (search?: string) =>
  queryOptions({
    queryKey: ["clients", search ?? ""],
    queryFn: async () =>
      (
        await ClientsService.readClients({
          query: {
            search: search || undefined,
            limit: PAGE_SIZE,
          },
        })
      ).data,
  })

export const getEmployeesQueryOptions = (search?: string) =>
  queryOptions({
    queryKey: ["employees", search ?? ""],
    queryFn: async () =>
      (
        await EmployeesService.readEmployees({
          query: {
            search: search || undefined,
            limit: PAGE_SIZE,
          },
        })
      ).data,
  })

export const getOrdersQueryOptions = (
  opts: { status?: OrderStatus | ""; search?: string } = {},
) =>
  queryOptions({
    queryKey: ["orders", opts.status ?? "", opts.search ?? ""],
    queryFn: async () =>
      (
        await OrdersService.readOrders({
          query: {
            status: opts.status || undefined,
            search: opts.search || undefined,
            limit: PAGE_SIZE,
          },
        })
      ).data,
  })

export const getOrderQueryOptions = (orderId: number) =>
  queryOptions({
    queryKey: ["orders", orderId],
    queryFn: async () =>
      (await OrdersService.readOrder({ path: { order_id: orderId } })).data,
  })

export const getOrderMatrixQueryOptions = (orderId: number) =>
  queryOptions({
    queryKey: ["orders", orderId, "matrix"],
    queryFn: async () =>
      (await OrdersService.readOrderMatrix({ path: { order_id: orderId } }))
        .data,
  })

export const getTerminalContextQueryOptions = () =>
  queryOptions({
    queryKey: ["terminal", "context"],
    queryFn: async () => (await TerminalService.readTerminalContext()).data,
    // Xato holatda (masalan postda ish markazi yo'q) admin tuzatgach terminal
    // o'zi tiklansin — operator sahifani qayta ochishni bilmasligi mumkin
    refetchInterval: 30_000,
  })

/** TABLO matritsasi — /tablo va boshqaruv paneli ikkalasi ham shu bitta so'rovdan
 *  oziqlanadi (avval har birida alohida yozilgan edi). */
export const getTabloMatrixQueryOptions = () =>
  queryOptions({
    queryKey: ["tablo", "matrix"],
    queryFn: async () => (await TabloService.readTabloMatrix()).data,
    refetchInterval: 60_000,
    // Devor ekrani hech qachon "fokusda" bo'lmaydi — hech kim sichqoncha
    // tegizmaydi, kiosk brauzeri boshqa oynaga o'tib qolishi mumkin. Standart
    // holatda TanStack fon oynada pollingni to'xtatadi: prodda o'lchandi —
    // ma'lumot 2 daqiqa eskirib, JONLI ko'rsatkichi bejiz qizarib qoldi.
    refetchIntervalInBackground: true,
  })

/** Status bo'yicha buyurtma sonlari. Reyestr tablari ham, sidebar badge'i ham
 *  shu bitta so'rovdan oziqlanadi — bir xil kalit, ya'ni TanStack dedupe qiladi. */
export const getOrderStatusCountsQueryOptions = () =>
  queryOptions({
    queryKey: ["orders", "status-counts"],
    queryFn: async () => (await OrdersService.readOrderStatusCounts()).data,
    refetchInterval: 30_000,
  })

/** MES agentlar — loglar sahifasi lug'at sifatida, printers sahifasi jonli
 *  ro'yxat sifatida ishlatadi. staleTime/refetchInterval har sahifaning o'zida
 *  (spread bilan): lug'atga 5 daqiqa kesh, jonli ro'yxatga 10s polling kerak. */
export const getBridgeAgentsQueryOptions = () =>
  queryOptions({
    queryKey: ["bridge-agents"],
    queryFn: async () => (await BridgeAgentsService.readBridgeAgents()).data,
  })

/**
 * CRUD mutatsiya callback triosi: muvaffaqiyat toast'i + xato toast'i +
 * keshni yangilash. Har dialogda qo'lda takrorlanadigan naqsh BITTA joyda.
 *
 * Dialog yopish kabi qo'shimcha ish chaqiruvchida:
 * `onSuccess: () => { cb.onSuccess(); onClose() }` tarzida o'raladi.
 */
export function crudCallbacks(
  queryClient: QueryClient,
  queryKey: unknown[],
  successMsg: string,
) {
  return {
    onSuccess: () => toast.success(successMsg),
    onError: handleError,
    onSettled: () => queryClient.invalidateQueries({ queryKey }),
  }
}
