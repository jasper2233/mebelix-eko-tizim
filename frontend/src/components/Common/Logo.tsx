import { Link } from "@tanstack/react-router"
import { useTheme } from "next-themes"

import { cn } from "@/lib/utils"
import icon from "/assets/logo/icon-navy.png"
import iconLight from "/assets/logo/icon-gold.png"
import logo from "/assets/logo/logo-navy.png"
import logoLight from "/assets/logo/logo-gold.png"

interface LogoProps {
  variant?: "full" | "icon" | "responsive"
  className?: string
  asLink?: boolean
}

export function Logo({
  variant = "full",
  className,
  asLink = true,
}: LogoProps) {
  const { resolvedTheme } = useTheme()
  const isDark = resolvedTheme === "dark"

  const fullLogo = isDark ? logoLight : logo
  const iconLogo = isDark ? iconLight : icon

  const content =
    variant === "responsive" ? (
      <>
        <img
          src={fullLogo}
          alt="MebeliX"
          className={cn(
            "h-6 w-auto group-data-[collapsible=icon]:hidden",
            className,
          )}
        />
        <img
          src={iconLogo}
          alt="MebeliX"
          className={cn(
            "h-5 w-auto hidden group-data-[collapsible=icon]:block",
            className,
          )}
        />
      </>
    ) : (
      <img
        src={variant === "full" ? fullLogo : iconLogo}
        alt="MebeliX"
        className={cn(variant === "full" ? "h-6 w-auto" : "h-5 w-auto", className)}
      />
    )

  if (!asLink) {
    return content
  }

  return <Link to="/">{content}</Link>
}
