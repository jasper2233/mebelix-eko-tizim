import { useRef } from "react"

/** Barmoq bilan SURIB aylantirish — tsex monoblokida scrollbar o'rniga.
 *
 * Monoblokning sensor drayveri barmoqni SICHQONCHA deb ko'rsatadi: barmoqni
 * surish brauzer uchun sichqoncha surishi bo'ladi, ya'ni ro'yxat aylanmaydi,
 * matn belgilanadi. Ingichka scrollbar'ni qo'lqopda tortish esa deyarli
 * imkonsiz. Shuning uchun surishni o'zimiz `scrollTop`/`scrollLeft` ga
 * o'giramiz.
 *
 * `pointerType === "touch"` bo'lsa TEGMAYMIZ: u yerda brauzerning o'zi
 * aylantiradi va ikkalasi bir vaqtda ishlasa ro'yxat ikki barobar tez
 * sirg'anardi. Ya'ni haqiqiy sensorli qurilmada xulq o'zgarmaydi, bu hook
 * faqat sichqoncha sifatida ko'rinadigan panel (va oddiy sichqoncha) uchun.
 *
 * Bosish bilan aralashmaydi: 8px dan ko'p surilsa bu SURISH deb hisoblanadi
 * va keyingi `click` yutiladi — aks holda ro'yxatni surganda tasodifan detal
 * ochilib ketardi.
 *
 * Gorizontal variantini `CutmapView` materiallar qatori ishlatadi.
 */
export function useDragScroll<T extends HTMLElement = HTMLDivElement>(
  axis: "x" | "y" = "y",
) {
  const ref = useRef<T>(null)
  const drag = useRef<{
    x: number
    y: number
    left: number
    top: number
    id: number
  } | null>(null)
  const surildi = useRef(false)

  const end = () => {
    drag.current = null
  }

  return {
    ref,
    props: {
      onPointerDown: (e: React.PointerEvent<T>) => {
        const el = ref.current
        // Haqiqiy sensor — brauzer o'zi aylantiradi, aralashmaymiz
        if (!el || e.pointerType === "touch") return
        surildi.current = false
        drag.current = {
          x: e.clientX,
          y: e.clientY,
          left: el.scrollLeft,
          top: el.scrollTop,
          id: e.pointerId,
        }
      },
      onPointerMove: (e: React.PointerEvent<T>) => {
        const el = ref.current
        const d = drag.current
        if (!el || !d || e.pointerId !== d.id) return
        const delta = axis === "x" ? e.clientX - d.x : e.clientY - d.y
        if (Math.abs(delta) < 8) return
        if (axis === "x") el.scrollLeft = d.left - delta
        else el.scrollTop = d.top - delta
        // SURISH deb faqat ro'yxat HAQIQATAN qimirlagani hisoblanadi. Sig'ib
        // turgan qisqa ro'yxatda (OVAL, STOLYARKA — prodda 8-10 qator)
        // aylantiriladigan joy yo'q, ya'ni barmoq qimirlasa ham bu bosish
        // bo'lib qolaveradi va detal ochilishi kerak.
        const moved =
          axis === "x" ? el.scrollLeft !== d.left : el.scrollTop !== d.top
        if (moved) surildi.current = true
      },
      onPointerUp: end,
      onPointerCancel: end,
      onPointerLeave: end,
      // Surishdan keyingi bosishni yutamiz — barmoq qator ustida uzilsa,
      // surish tasodifan tanlovga aylanardi.
      onClickCapture: (e: React.MouseEvent) => {
        if (!surildi.current) return
        e.preventDefault()
        e.stopPropagation()
        surildi.current = false
      },
    },
  }
}
