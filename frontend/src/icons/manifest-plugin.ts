// Web app manifest — BUILD'DA yoziladi, ikonka yo'llari hash'li.
//
// Nega: ikonka fayllari `public/` da hash'siz nom bilan turganda brauzer
// (va iOS Home Screen) birinchi ko'rgan versiyani 1 yil «immutable» kesh
// bilan ushlab qolardi — 2026-09-04 da ikonka uch marta o'zgardi, har
// qurilma/profil boshqa-boshqa versiyani ko'rsatdi. Vite import qilingan
// rasmga content-hash qo'yadi (`icon-512-Ab3x9c.png`); ikonka o'zgarsa URL
// ham o'zgaradi — eski keshga hech kim ilinmaydi. Manifest o'zi hash'siz
// (`/manifest.webmanifest`, nginx `no-cache`), ichidagi yo'llar hash'li.
//
// Service worker ATAYLAB yo'q — sabab docs/05 da.
import type { Plugin, ResolvedConfig } from "vite"

const ICONS = [
  { file: "icon-192.png", sizes: "192x192", purpose: "any" },
  { file: "icon-512.png", sizes: "512x512", purpose: "any" },
  { file: "icon-192-maskable.png", sizes: "192x192", purpose: "maskable" },
  { file: "icon-512-maskable.png", sizes: "512x512", purpose: "maskable" },
] as const

export function webManifest(): Plugin {
  let config: ResolvedConfig
  return {
    name: "mebelix-web-manifest",
    configResolved(c) {
      config = c
    },
    // Dev: fayllar hash'siz, to'g'ridan-to'g'ri `src/icons/` dan
    configureServer(server) {
      server.middlewares.use("/manifest.webmanifest", (_req, res) => {
        res.setHeader("Content-Type", "application/manifest+json")
        res.end(
          JSON.stringify(
            manifest(ICONS.map((i) => `/src/icons/${i.file}`)),
            null,
            2,
          ),
        )
      })
    },
    // Build: ikonkalar emit qilinadi (hash'li nom), manifest o'sha nomlar bilan
    async generateBundle() {
      const { readFile } = await import("node:fs/promises")
      const { resolve } = await import("node:path")
      const urls: string[] = []
      for (const i of ICONS) {
        const ref = this.emitFile({
          type: "asset",
          name: i.file,
          source: await readFile(resolve(config.root, "src/icons", i.file)),
        })
        urls.push(`${config.base}${this.getFileName(ref)}`)
      }
      this.emitFile({
        type: "asset",
        fileName: "manifest.webmanifest",
        source: JSON.stringify(manifest(urls), null, 2),
      })
    },
  }
}

function manifest(iconUrls: string[]) {
  return {
    name: "MebeliX MES",
    short_name: "MebeliX",
    id: "/",
    start_url: "/",
    scope: "/",
    display: "fullscreen",
    orientation: "landscape",
    lang: "uz",
    background_color: "#16233a",
    theme_color: "#16233a",
    icons: ICONS.map((i, n) => ({
      src: iconUrls[n],
      sizes: i.sizes,
      type: "image/png",
      purpose: i.purpose,
    })),
  }
}
