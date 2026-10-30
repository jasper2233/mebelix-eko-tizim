import { type ReactNode, useState } from "react"

import { ConfirmDialog } from "@/components/Common/ConfirmDialog"

type So_rov = {
  title: ReactNode
  description?: ReactNode
  confirmText?: string
  destructive?: boolean
  onConfirm: () => void
}

/** Qaytarib bo'lmaydigan amal oldidan bitta umumiy savol (davr yopish, vedomost tasdiqlash, ESF yuborish,
 *  storno…). Ekran oynani o'zi chizadi: `const [tasdiqOyna, sora] = useTasdiq()` → `{tasdiqOyna}` va
 *  `onClick={() => sora({ title, description, onConfirm })}`. Oyna amal tanlangach darhol yopiladi —
 *  natija (xato yoki muvaffaqiyat) ekranning o'z joyida ko'rinadi. */
export function useTasdiq(): [ReactNode, (s: So_rov) => void] {
  const [s, setS] = useState<So_rov | null>(null)
  const oyna = (
    <ConfirmDialog
      open={s != null}
      onOpenChange={(o) => !o && setS(null)}
      title={s?.title}
      description={s?.description}
      confirmText={s?.confirmText}
      destructive={s?.destructive}
      onConfirm={() => {
        s?.onConfirm()
        setS(null)
      }}
    />
  )
  return [oyna, setS]
}
