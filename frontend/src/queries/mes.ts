import { type QueryClient, queryOptions } from "@tanstack/react-query"
import { toast } from "sonner"

import {
  BridgeAgentsService,
  ClientsService,
  EmployeesService,
  MachinesService,
  OrdersService,
  PostsService,
  StockService,
  TabloService,
  TerminalService,
} from "@/client"
import { handleError } from "@/utils"

// Small reference sets are fetched whole; registries pull up to the backend max page.
export const PAGE_SIZE = 100 // backend MAX_PAGE_SIZE

export const getPostsQueryOptions = () =>
  queryOptions({
    queryKey: ["posts"],
    queryFn: () => PostsService.readPosts(),
    staleTime: 5 * 60_000,
  })

export const getMachinesQueryOptions = () =>
  queryOptions({
    queryKey: ["machines"],
    queryFn: () => MachinesService.readMachines(),
    staleTime: 60_000,
  })

export const getClientsQueryOptions = (search?: string) =>
  queryOptions({
    queryKey: ["clients", search ?? ""],
    queryFn: () =>
      ClientsService.readClients({
        search: search || undefined,
        limit: PAGE_SIZE,
      }),
  })

export const getEmployeesQueryOptions = (search?: string) =>
  queryOptions({
    queryKey: ["employees", search ?? ""],
    queryFn: () =>
      EmployeesService.readEmployees({
        search: search || undefined,
        limit: PAGE_SIZE,
      }),
  })

export const getOrdersQueryOptions = (
  opts: { status?: string; search?: string; page?: number } = {},
) =>
  queryOptions({
    queryKey: ["orders", opts.status ?? "", opts.search ?? "", opts.page ?? 0],
    queryFn: () =>
      OrdersService.readOrders({
        status: (opts.status as never) || undefined,
        search: opts.search || undefined,
        skip: (opts.page ?? 0) * PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
  })

export const getOrderQueryOptions = (orderId: number) =>
  queryOptions({
    queryKey: ["orders", orderId],
    queryFn: () => OrdersService.readOrder({ orderId }),
  })

export const getOrderMatrixQueryOptions = (orderId: number) =>
  queryOptions({
    queryKey: ["orders", orderId, "matrix"],
    queryFn: () => OrdersService.readOrderMatrix({ orderId }),
  })

export const getTerminalContextQueryOptions = () =>
  queryOptions({
    queryKey: ["terminal", "context"],
    queryFn: () => TerminalService.readTerminalContext(),
    // Xato holatda (masalan postda ish markazi yo'q) admin tuzatgach terminal
    // o'zi tiklansin — operator sahifani qayta ochishni bilmasligi mumkin
    refetchInterval: 30_000,
  })

/** TABLO matritsasi — /tablo va boshqaruv paneli ikkalasi ham shu bitta so'rovdan
 *  oziqlanadi (avval har birida alohida yozilgan edi). */
export const getTabloMatrixQueryOptions = () =>
  queryOptions({
    queryKey: ["tablo", "matrix"],
    queryFn: () => TabloService.readTabloMatrix(),
    refetchInterval: 60_000,
  })

/** Status bo'yicha buyurtma sonlari. Reyestr tablari ham, sidebar badge'i ham
 *  shu bitta so'rovdan oziqlanadi — bir xil kalit, ya'ni TanStack dedupe qiladi. */
export const getOrderStatusCountsQueryOptions = () =>
  queryOptions({
    queryKey: ["orders", "status-counts"],
    queryFn: () => OrdersService.readOrderStatusCounts(),
    refetchInterval: 30_000,
  })

/** Printer agentlar — loglar sahifasi lug'at sifatida, printers sahifasi jonli
 *  ro'yxat sifatida ishlatadi. staleTime/refetchInterval har sahifaning o'zida
 *  (spread bilan): lug'atga 5 daqiqa kesh, jonli ro'yxatga 10s polling kerak. */
export const getBridgeAgentsQueryOptions = () =>
  queryOptions({
    queryKey: ["bridge-agents"],
    queryFn: () => BridgeAgentsService.readBridgeAgents(),
  })

/**
 * CRUD mutatsiya callback triosi: muvaffaqiyat toast'i + xato toast'i +
 * keshni yangilash. Har dialogda qo'lda takrorlanadigan naqsh BITTA joyda.
 *
 * Dialog yopish kabi qo'shimcha ish chaqiruvchida:
 * `onSuccess: () => { cb.onSuccess(); onClose() }` tarzida o'raladi.
 */
/** Materiallar ombori. Guruh chiplari va tepadagi raqamlar AYRIM so'rovlar:
 * ular sahifalashdan mustaqil — 638 tovarning 100 tasi ko'rinib turganda
 * ham "12 ta tovar tugayapti" butun ombor bo'yicha bo'lishi kerak. */
export const getStockQueryOptions = (opts: {
  search?: string
  catalog?: "F" | "M"
  groupCode?: string
  low?: boolean
  page?: number
}) =>
  queryOptions({
    queryKey: [
      "stock",
      opts.search ?? "",
      opts.catalog ?? "",
      opts.groupCode ?? "",
      opts.low ?? false,
      opts.page ?? 0,
    ],
    queryFn: () =>
      StockService.readStockItems({
        search: opts.search || undefined,
        catalog: opts.catalog,
        groupCode: opts.groupCode || undefined,
        low: opts.low || undefined,
        skip: (opts.page ?? 0) * PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
  })

export const getStockGroupsQueryOptions = () =>
  queryOptions({
    queryKey: ["stock", "groups"],
    queryFn: () => StockService.readStockGroups(),
  })

export const getStockSummaryQueryOptions = () =>
  queryOptions({
    queryKey: ["stock", "summary"],
    queryFn: () => StockService.readStockSummary(),
  })

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
