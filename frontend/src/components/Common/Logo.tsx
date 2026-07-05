import { Link } from "@tanstack/react-router"

import { cn } from "@/lib/utils"
import iconGold from "/assets/logo/icon-gold.png"
import iconNavy from "/assets/logo/icon-navy.png"
import logoGold from "/assets/logo/logo-gold.png"
import logoNavy from "/assets/logo/logo-navy.png"

interface LogoProps {
  variant?: "full" | "icon" | "responsive"
  /** navy on light surfaces, gold on navy surfaces */
  tone?: "navy" | "gold"
  className?: string
  asLink?: boolean
}

export function Logo({
  variant = "full",
  tone = "navy",
  className,
  asLink = true,
}: LogoProps) {
  const logo = tone === "gold" ? logoGold : logoNavy
  const icon = tone === "gold" ? iconGold : iconNavy

  const content =
    variant === "responsive" ? (
      <>
        <img
          src={logo}
          alt="MebeliX"
          className={cn(
            "h-8 w-auto group-data-[collapsible=icon]:hidden",
            className,
          )}
        />
        <img
          src={icon}
          alt="MebeliX"
          className={cn(
            "h-6 w-auto hidden group-data-[collapsible=icon]:block",
            className,
          )}
        />
      </>
    ) : (
      <img
        src={variant === "full" ? logo : icon}
        alt="MebeliX"
        className={cn(
          variant === "full" ? "h-6 w-auto" : "h-5 w-auto",
          className,
        )}
      />
    )

  if (!asLink) {
    return content
  }

  return <Link to="/">{content}</Link>
}
