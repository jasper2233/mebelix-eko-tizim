// Tizim sozlamalari: ish vaqtida admin o'zgartiradigan qiymatlar. Hozircha
// bittasi — nostandart detal belgisi; keyin stanoklar sozlamalari shu yerga
// qo'shiladi (shuning uchun sahifa "Nostandart belgi" emas, "Tizim sozlamalari").

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useEffect, useState } from "react"

import { SettingsService } from "@/client"
import { Field } from "@/components/Common/Field"
import { PageHeader } from "@/components/Common/PageHeader"
import { QueryError } from "@/components/Common/QueryError"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { Skeleton } from "@/components/ui/skeleton"
import { requireAccess } from "@/lib/guards"
import { isAdmin } from "@/lib/mes"
import { crudCallbacks } from "@/queries/mes"

export const Route = createFileRoute("/_layout/system-settings")({
  component: SystemSettingsPage,
  // `lib/mes` dagi `isAdmin` izohi shu sahifani nomma-nom sanab o'tadi
  beforeLoad: requireAccess(isAdmin),
  head: () => ({ meta: [{ title: "Tizim sozlamalari | MebeliX" }] }),
})

const SUFFIX_KEY = "custom_part_suffix"

function SystemSettingsPage() {
  const queryClient = useQueryClient()
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["system-settings"],
    queryFn: async () => (await SettingsService.readSystemSettings()).data,
  })
  const saqlangan = data?.find((s) => s.key === SUFFIX_KEY)?.value ?? ""
  const [suffix, setSuffix] = useState("")
  // Server qiymati kelgach maydon bir marta to'ldiriladi; keyin foydalanuvchi
  // yozayotganini 60s refetch bosib ketmasin.
  useEffect(() => setSuffix(saqlangan), [saqlangan])

  const mutation = useMutation({
    mutationFn: () =>
      SettingsService.updateSystemSetting({
        path: { key: SUFFIX_KEY },
        body: { value: suffix.trim() },
      }),
    ...crudCallbacks(queryClient, ["system-settings"], "Sozlama saqlandi"),
  })

  return (
    <div>
      <PageHeader
        title="Tizim sozlamalari"
        description="Ish vaqtida o'zgaradigan qiymatlar — konteynerni qayta ishga tushirish shart emas."
      />
      {isLoading ? (
        <Skeleton className="h-32 w-full max-w-xl" />
      ) : isError ? (
        <QueryError onRetry={() => refetch()} />
      ) : (
        <div className="max-w-xl space-y-4 rounded-lg border bg-card p-4">
          <Field label="Nostandart detal belgisi">
            <Input
              value={suffix}
              maxLength={8}
              placeholder="#"
              onChange={(e) => setSuffix(e.target.value)}
            />
          </Field>
          <p className="text-sm text-muted-foreground">
            Bazisda detal nomi shu belgi bilan tugasa, u yuklashda{" "}
            <b>nostandart</b> deb belgilanadi va fayldan avtomatik marshrut
            olmaydi — marshrutini texnolog «Nostandart detallar» tabida chizadi.
            Belgi detal nomida qoladi, ya'ni chekda ham ko'rinadi. Qo'lda
            belgilash o'z joyida: matritsadagi «Nostandart» ustuni.
          </p>
          <p className="text-sm text-muted-foreground">
            Bo'sh qoldirilsa qoida <b>o'chadi</b> — hech bir detal avtomatik
            belgilanmaydi. Qoida faqat YANGI yuklashda ishlaydi, mavjud
            buyurtmalarga tegmaydi.
          </p>
          <LoadingButton
            loading={mutation.isPending}
            disabled={suffix.trim() === saqlangan.trim()}
            onClick={() => mutation.mutate()}
          >
            Saqlash
          </LoadingButton>
        </div>
      )}
    </div>
  )
}
