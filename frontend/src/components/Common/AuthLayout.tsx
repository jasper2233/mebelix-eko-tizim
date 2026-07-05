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
          className="pointer-events-none absolute -right-24 -bottom-16 w-[28rem] rotate-[-8deg] opacity-[0.07]"
        />
        <Logo variant="full" tone="gold" className="h-16" asLink={false} />
      </div>
      <div className="flex flex-col gap-4 p-6 md:p-10">
        <div className="flex flex-1 items-center justify-center">
          <div className="w-full max-w-xs">{children}</div>
        </div>
        <Footer />
      </div>
    </div>
  )
}
