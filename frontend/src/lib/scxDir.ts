// SCX fayllar uchun doimiy papka: stanok kompyuterida BIR MARTA
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
export async function getSavedDir(): Promise<FileSystemDirectoryHandle | null> {
  try {
    const h = await kvGet<FileSystemDirectoryHandle>(KEY)
    if (!h) return null
    // TS lib'da hali yo'q (Chrome API) — shuning uchun tor lokal tip
    const perms = h as unknown as {
      queryPermission: (o: { mode: string }) => Promise<string>
      requestPermission: (o: { mode: string }) => Promise<string>
    }
    let perm = await perms.queryPermission({ mode: "readwrite" })
    if (perm !== "granted")
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
  } catch (e) {
    // Faqat bekor qilish "jim" qaytadi; SecurityError/NotAllowedError kabi
    // haqiqiy nosozlik chaqiruvchiga chiqsin — aks holda tugma jimgina o'lik
    if ((e as DOMException)?.name === "AbortError") return null
    throw e
  }
}

/** SCX faylni serverdan olib papkaga yozadi; yozilgan fayl nomini qaytaradi (xatoda throw).
 * Nomni chaqiruvchi beradi — docs/11 bo'yicha SCX fayl nomi QR matnining o'zi. */
export async function saveScxToDir(
  dir: FileSystemDirectoryHandle,
  fileId: number,
  filename: string,
): Promise<string> {
  const resp = await fetch(scxFileUrl(fileId), {
    credentials: "include",
  })
  if (!resp.ok) throw new Error(`Fayl ${fileId}: HTTP ${resp.status}`)
  const blob = await resp.blob()
  const fh = await dir.getFileHandle(filename, { create: true })
  const w = await fh.createWritable()
  await w.write(blob)
  await w.close()
  return filename
}
