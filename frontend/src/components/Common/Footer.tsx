export function Footer() {
  const currentYear = new Date().getFullYear()

  return (
    <footer className="px-6 py-4">
      <p className="text-muted-foreground text-center text-sm">
        MebeliX MES · {currentYear}
      </p>
    </footer>
  )
}
