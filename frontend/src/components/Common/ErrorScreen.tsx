import { Link } from "@tanstack/react-router"
import { Button } from "@/components/ui/button"

/** Xato/404 ekranlari bitta maketdan — ikki nusxa layout drift bermasin */
export function ErrorScreen({
  code,
  message,
}: {
  code: string
  message: string
}) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-4">
      <span className="mb-4 text-6xl font-bold leading-none md:text-8xl">
        {code}
      </span>
      <p className="mb-4 text-center text-lg text-muted-foreground">
        {message}
      </p>
      <Link to="/">
        <Button>Bosh sahifaga</Button>
      </Link>
    </div>
  )
}
