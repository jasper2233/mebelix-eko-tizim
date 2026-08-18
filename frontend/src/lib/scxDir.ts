// SCX fayllar uchun doimiy papka (TZ 12.5): stanok kompyuterida BIR MARTA
// tanlanadi (File System Access API), IndexedDB'da saqlanadi — keyingi yuklab
// olishlar so'roqsiz o'sha papkaga tushadi. API bo'lmasa (eski brauzer)
// chaqiruvchi oddiy <a download> ga qaytadi.

import { API_BASE } from "@/utils"

const DB_NAME = "mebelix-terminal"
const STORE = "kv"
const KEY = "scx-dir"

function idb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1)
    req.onupgradeneeded = () => req.result.createObjectStore(STORE)
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

async function kvGet<T>(key: string): Promise<T | undefined> {
  const db = await idb()
  return new Promise((resolve, reject) => {
    const req = db.transaction(STORE).objectStore(STORE).get(key)
    req.onsuccess = () => resolve(req.result as T | undefined)
    req.onerror = () => reject(req.error)
  })
}

async function kvSet(key: string, value: unknown): Promise<void> {
  const db = await idb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite")
    tx.objectStore(STORE).put(value, key)
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
  })
}

export function dirSupported(): boolean {
  return "showDirectoryPicker" in window
}

/** SCX faylni yuklab olish URL'i — endpoint manzili BITTA joyda */
export function scxFileUrl(id: number): string {
  return `${API_BASE}/api/v1/terminal/files/${id}`
}

/** Proyekt nomidan papka nomi: Windows'da taqiqlangan belgilar almashtiriladi */
export function projectFolder(name: string): string {
  return name.replace(/[\\/:*?"<>|]/g, "_").trim()
}

/** Saqlangan papka (ruxsati tekshirilgan holda); yo'q yoki ruxsat berilmagan — null */
export async function getSavedDir(
  requestIfNeeded: boolean,
): Promise<FileSystemDirectoryHandle | null> {
  try {
    const h = await kvGet<FileSystemDirectoryHandle>(KEY)
    if (!h) return null
    // TS lib'da hali yo'q (Chrome API) — shuning uchun tor lokal tip
    const perms = h as unknown as {
      queryPermission: (o: { mode: string }) => Promise<string>
      requestPermission: (o: { mode: string }) => Promise<string>
    }
    let perm = await perms.queryPermission({ mode: "readwrite" })
    if (perm !== "granted" && requestIfNeeded)
      perm = await perms.requestPermission({ mode: "readwrite" })
    return perm === "granted" ? h : null
  } catch {
    return null
  }
}

/** Papka tanlash dialogi — tanlangani saqlanadi (bir marta so'raladi) */
export async function pickDir(): Promise<FileSystemDirectoryHandle | null> {
  try {
    const h = await (
      window as unknown as {
        showDirectoryPicker: (o: {
          mode: string
        }) => Promise<FileSystemDirectoryHandle>
      }
    ).showDirectoryPicker({ mode: "readwrite" })
    await kvSet(KEY, h)
    return h
  } catch {
    return null // foydalanuvchi bekor qildi
  }
}

/** SCX faylni serverdan olib papkaga yozadi; yozilgan fayl nomini qaytaradi (xatoda throw) */
export async function saveScxToDir(
  dir: FileSystemDirectoryHandle,
  fileId: number,
  filename?: string,
): Promise<string> {
  const resp = await fetch(scxFileUrl(fileId), {
    credentials: "include",
  })
  if (!resp.ok) throw new Error(`Fayl ${fileId}: HTTP ${resp.status}`)
  let name = filename
  if (!name) {
    const cd = resp.headers.get("content-disposition") ?? ""
    name = /filename="?([^";]+)"?/.exec(cd)?.[1] ?? `scx_${fileId}.scx`
  }
  const blob = await resp.blob()
  const fh = await dir.getFileHandle(name, { create: true })
  const w = await fh.createWritable()
  await w.write(blob)
  await w.close()
  return name
}

/** Bitta SCX: saqlangan papkaga — folder berilsa proyekt nomli subpapkaga
 * ("Hammasini yuklab olish" bilan BIR joy); papka yo'q — brauzer Downloads */
export async function downloadScx(
  fileId: number,
  folder?: string | null,
): Promise<void> {
  if (dirSupported()) {
    const dir = await getSavedDir(false)
    if (dir) {
      try {
        const target = folder
          ? await dir.getDirectoryHandle(projectFolder(folder), {
              create: true,
            })
          : dir
        await saveScxToDir(target, fileId)
        return
      } catch {
        /* papka o'chirilgan bo'lishi mumkin — quyidagi fallback */
      }
    }
  }
  const a = document.createElement("a")
  a.href = scxFileUrl(fileId)
  a.download = ""
  a.click()
}
