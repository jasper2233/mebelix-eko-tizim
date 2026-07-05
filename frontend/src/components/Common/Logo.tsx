import { Link } from "@tanstack/react-router"

import { cn } from "@/lib/utils"
import icon from "/assets/logo/icon-navy.png"
import logo from "/assets/logo/logo-navy.png"

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
  const content =
    variant === "responsive" ? (
      <>
        <img
          src={logo}
          alt="MebeliX"
          className={cn(
            "h-6 w-auto group-data-[collapsible=icon]:hidden",
            className,
          )}
        />
        <img
          src={icon}
          alt="MebeliX"
          className={cn(
            "h-5 w-auto hidden group-data-[collapsible=icon]:block",
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
