import { Link } from "@tanstack/react-router"
import { Button } from "@/components/ui/button"

const ErrorComponent = () => {
  return (
    <div className="flex min-h-screen items-center justify-center flex-col p-4">
      <div className="flex items-center z-10">
        <div className="flex flex-col ml-4 items-center justify-center p-4">
          <span className="text-6xl md:text-8xl font-bold leading-none mb-4">
            Xato
          </span>
          <span className="text-2xl font-bold mb-2">Voy!</span>
        </div>
      </div>

      <p className="text-lg text-muted-foreground mb-4 text-center z-10">
        Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.
      </p>
      <Link to="/">
        <Button>Bosh sahifaga</Button>
      </Link>
    </div>
  )
}

export default ErrorComponent
