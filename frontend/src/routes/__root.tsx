import { ReactQueryDevtools } from "@tanstack/react-query-devtools"
import {
  createRootRoute,
  HeadContent,
  Outlet,
  useRouterState,
} from "@tanstack/react-router"
import { TanStackRouterDevtools } from "@tanstack/react-router-devtools"
import ErrorComponent from "@/components/Common/ErrorComponent"
import NotFound from "@/components/Common/NotFound"
import { Toaster } from "@/components/ui/sonner"

// Sex ekranida (terminal/tablo) toast MARKAZ-TEPADA va katta shriftda —
// operator monitordan 2-3 metr narida turadi, burchakdagi mayda yozuvni
// o'qiy olmaydi (HMI amaliyoti). Ofis sahifalarida odatdagi burchak qoladi.
function AppToaster() {
  const path = useRouterState({ select: (s) => s.location.pathname })
  const operator = path.startsWith("/terminal") || path.startsWith("/tablo")
  return (
    <Toaster
      richColors
      closeButton
      position={operator ? "top-center" : "bottom-right"}
      duration={operator ? 6000 : 4000}
      toastOptions={
        operator
          ? {
              style: {
                fontSize: "1.3rem",
                padding: "20px 24px",
                width: "560px",
              },
            }
          : undefined
      }
    />
  )
}

export const Route = createRootRoute({
  component: () => (
    <>
      <HeadContent />
      <Outlet />
      <AppToaster />
      <TanStackRouterDevtools position="bottom-right" />
      <ReactQueryDevtools initialIsOpen={false} />
    </>
  ),
  notFoundComponent: () => <NotFound />,
  errorComponent: () => <ErrorComponent />,
})
