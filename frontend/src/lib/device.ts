// Sexdagi monoblok "bog'langan qurilma" ekanini shu yerda eslab qoladi.
//
// Nega umuman kerak: operator login parolsiz, faqat beyjik skani bilan kiradi.
// Beyjik QR qog'ozda — suratga olsa bo'ladi. Qurilma tokeni shu QR'ni SEXGA
// bog'lab qo'yadi: token bo'lmagan brauzerda beyjik hech nima ochmaydi.
//
// localStorage: token muddatsiz va qurilmaga tegishli, ya'ni sessiya emas —
// monoblok o'chib yonganda ham qolishi kerak.

const KEY = "mx.device"

export type PairedDevice = {
  token: string
  machineName: string
  postName: string
}

export function pairedDevice(): PairedDevice | null {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return null
    const d = JSON.parse(raw) as Partial<PairedDevice>
    return d.token
      ? {
          token: d.token,
          machineName: d.machineName ?? "",
          postName: d.postName ?? "",
        }
      : null
  } catch {
    return null // buzilgan yozuv = bog'lanmagan qurilma
  }
}

export function savePairedDevice(d: PairedDevice) {
  localStorage.setItem(KEY, JSON.stringify(d))
}

export function clearPairedDevice() {
  localStorage.removeItem(KEY)
}
