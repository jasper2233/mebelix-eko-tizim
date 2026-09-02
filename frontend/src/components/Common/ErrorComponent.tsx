import type { ErrorComponentProps } from "@tanstack/react-router"
import { Button } from "@/components/ui/button"
import { extractErrorMessage } from "@/utils"
import { ErrorScreen } from "./ErrorScreen"

/** Router'ning uncaught xatosi. `error`/`reset` — TanStack beradigan proplar:
 * sababsiz umumiy jumla operatorga ham, texnologga ham hech nima aytmaydi. */
export const ErrorComponent = ({ error, reset }: ErrorComponentProps) => (
  <ErrorScreen
    code="Xato"
    message="Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring."
    detail={extractErrorMessage(error)}
    action={
      <Button variant="outline" onClick={reset}>
        Qayta urinish
      </Button>
    }
  />
)
