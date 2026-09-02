import { Link } from "@tanstack/react-router"
import type { ReactNode } from "react"
import { Button } from "@/components/ui/button"

/** Xato/404 ekranlari bitta maketdan — ikki nusxa layout drift bermasin */
export function ErrorScreen({
  code,
  message,
  detail,
  action,
}: {
  code: string
  message: string
  /** Sabab (server xabari) — umumiy matn ostida mayda shriftda */
  detail?: string
  /** "Bosh sahifaga" yonidagi qo'shimcha tugma (masalan, qayta urinish) */
  action?: ReactNode
}) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-4">
      <span className="mb-4 text-6xl font-bold leading-none md:text-8xl">
        {code}
      </span>
      <p className="mb-4 text-center text-lg text-muted-foreground">
        {message}
      </p>
      {detail ? (
        <p className="mb-4 max-w-md text-center text-sm text-muted-foreground">
          {detail}
        </p>
      ) : null}
      <div className="flex flex-wrap items-center justify-center gap-2">
        {action}
        <Button asChild>
          <Link to="/">Bosh sahifaga</Link>
        </Button>
      </div>
    </div>
  )
}
