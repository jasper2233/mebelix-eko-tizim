import { Logo } from "@/components/Common/Logo"
import { Footer } from "./Footer"

interface AuthLayoutProps {
  children: React.ReactNode
}

export function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <div className="grid min-h-svh lg:grid-cols-2">
      <div className="relative hidden overflow-hidden bg-gradient-to-b from-[#2f496e] to-[#1c2e49] lg:flex lg:items-center lg:justify-center">
        <img
          src="/assets/logo/icon-gold.png"
          alt=""
          aria-hidden="true"
          className="pointer-events-none absolute -right-14 -bottom-14 w-[26rem] opacity-[0.09] select-none"
        />
        <Logo variant="full" tone="gold" className="h-24" asLink={false} />
      </div>
      <div className="relative overflow-hidden flex flex-col gap-4 p-6 md:p-10">
        <img
          src="/assets/logo/icon-navy.png"
          alt=""
          aria-hidden="true"
          className="pointer-events-none absolute -right-12 -bottom-12 w-72 opacity-[0.05] select-none lg:hidden"
        />
        <div className="flex flex-1 items-center justify-center">
          <div className="w-full max-w-md">{children}</div>
        </div>
        <Footer />
      </div>
    </div>
  )
}
