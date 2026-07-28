import { queryOptions } from "@tanstack/react-query"

import {
  AuditService,
  ClientsService,
  EmployeesService,
  MachinesService,
  MaterialsService,
  OrdersService,
  PostsService,
  TabloService,
  TerminalService,
} from "@/client"

// Small reference sets are fetched whole; registries pull up to the backend max page.
const PAGE = 100

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
      ClientsService.readClients({ search: search || undefined, limit: PAGE }),
  })

export const getEmployeesQueryOptions = (search?: string) =>
  queryOptions({
    queryKey: ["employees", search ?? ""],
    queryFn: () =>
      EmployeesService.readEmployees({
        search: search || undefined,
        limit: PAGE,
      }),
  })

export const getMaterialsQueryOptions = (
  search?: string,
  type?: "sheet" | "band" | "hardware",
) =>
  queryOptions({
    queryKey: ["materials", search ?? "", type ?? ""],
    queryFn: () =>
      MaterialsService.readMaterials({
        search: search || undefined,
        type,
        limit: PAGE,
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
        skip: (opts.page ?? 0) * PAGE,
        limit: PAGE,
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

export const getAuditLogsQueryOptions = (
  opts: { module?: string; page?: number } = {},
) =>
  queryOptions({
    queryKey: ["audit", opts.module ?? "", opts.page ?? 0],
    queryFn: () =>
      AuditService.readAuditLogs({
        module: opts.module || undefined,
        skip: (opts.page ?? 0) * PAGE,
        limit: PAGE,
      }),
  })

export const getTerminalContextQueryOptions = () =>
  queryOptions({
    queryKey: ["terminal", "context"],
    queryFn: () => TerminalService.readTerminalContext(),
  })

export const getTerminalTasksQueryOptions = () =>
  queryOptions({
    queryKey: ["terminal", "tasks"],
    queryFn: () => TerminalService.readTerminalTasks(),
    refetchInterval: 30_000, // WS is the primary trigger; this is the safety net
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
