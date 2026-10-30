/** Ctrl+K qidiruv oynasini ochish hodisasi (`Common/CommandPalette` tinglaydi; sidebar tugmasi yuboradi).
 *  Alohida faylda: palitra sidebar menyusini (NAV_ITEMS) o'qiydi — aylanma import bo'lmasin. */
export const QIDIRUV_OCHISH = "mebelix:qidiruv"

export function openCommandPalette() {
  window.dispatchEvent(new Event(QIDIRUV_OCHISH))
}
