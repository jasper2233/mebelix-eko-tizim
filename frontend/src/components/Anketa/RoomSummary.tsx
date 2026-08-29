// Texnolog/direktor ko'rinishi: anketa FORMA emas, o'qish uchun jamlanma —
// matn nusxa olinadi.
//
// DIQQAT: bu ko'rinish `anketa.$orderId.tsx` dagi forma bilan BIR XIL
// ma'lumotni chizadi. Anketaga yangi maydon qo'shilsa, u shu yerda ham
// ko'rinishi kerak — aks holda texnolog uni umuman ko'rmaydi.

import type { OrderFileRead, OrderSurvey, SurveyRoom } from "@/client"
import { Facts, Section } from "@/components/Anketa/fields"
import { RoomPhotos } from "@/components/Anketa/RoomPhotos"
import {
  CORPUS_MATERIALS,
  CORPUS_THICKNESS,
  COUNTERTOPS,
  EXTRA_SERVICES,
  FACADE_MATERIALS,
  FURNITURE_TYPES,
  HARDWARE_LEVELS,
  LAYOUT_SHAPES,
  labelOf,
  labelsOf,
  ORDER_SERVICES,
} from "@/lib/anketa"

export function RoomSummary({
  room,
  survey,
  orderId,
  photos,
}: {
  room: SurveyRoom
  survey: OrderSurvey
  orderId: number
  photos: OrderFileRead[]
}) {
  const dims = [room.room_length, room.room_width, room.room_height]
  const walls = (room.walls ?? []).filter((w) => w.length || w.height)
  const modules = room.modules ?? []

  return (
    <div className="space-y-5">
      {/* Qaysi xona ekani — texnolog buni bilmasa noto'g'ri o'lchamda modul yasaydi */}
      <h2 className="text-base font-semibold">{room.name || "Xona"}</h2>

      <Section title={`Modullar (${modules.length} ta)`}>
        {modules.length ? (
          <div className="overflow-x-auto">
            {/* biome-ignore lint/correctness/noRestrictedElements: anketa jadvali reyestr emas — kataklarida kiritish maydonlari turadi, o'z ustun kengliklari bilan */}
            <table className="w-full min-w-[700px] border-collapse text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground text-xs font-semibold uppercase tracking-wider">
                  <th className="w-8 py-2">№</th>
                  <th className="py-2">Nomi</th>
                  <th className="w-16 py-2">Devor</th>
                  <th className="w-20 py-2 text-right">Eni, mm</th>
                  <th className="w-20 py-2 text-right">Chuq., mm</th>
                  <th className="w-20 py-2 text-right">Bal., mm</th>
                  <th className="w-16 py-2 text-right">Soni</th>
                  <th className="py-2">Izoh</th>
                </tr>
              </thead>
              <tbody>
                {modules.map((m, i) => (
                  <tr key={`${m.name}-${i}`} className="border-b">
                    <td className="py-2 text-muted-foreground">{i + 1}</td>
                    <td className="py-2 font-medium">{m.name || "—"}</td>
                    <td className="py-2">{m.wall || "—"}</td>
                    <td className="py-2 text-right num">{m.width ?? "—"}</td>
                    <td className="py-2 text-right num">{m.depth ?? "—"}</td>
                    <td className="py-2 text-right num">{m.height ?? "—"}</td>
                    <td className="py-2 text-right num">{m.count ?? "—"}</td>
                    <td className="py-2 text-muted-foreground">
                      {m.note || ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-muted-foreground text-sm">
            Modullar kiritilmagan — o'lchov varag'i hali to'ldirilmagan.
          </p>
        )}
        {(room.total_running_meters != null || room.total_height != null) && (
          <p className="mt-2 text-muted-foreground text-sm">
            Umumiy: {room.total_running_meters ?? "—"} pm ·{" "}
            {room.total_height ?? "—"} mm balandlik
          </p>
        )}
      </Section>

      <RoomPhotos
        orderId={orderId}
        roomId={room.id}
        photos={photos}
        canEdit={false}
      />

      <Section title="Xona o'lchamlari">
        <Facts
          items={[
            [
              "Xona (uz × ken × bal)",
              dims.every((d) => d == null)
                ? ""
                : `${dims.map((d) => d ?? "?").join(" × ")} mm`,
            ],
            [
              "Mebel devori",
              room.furniture_wall_length
                ? `${room.furniture_wall_length} mm`
                : "",
            ],
            ["Shakl", room.shape ? labelOf(LAYOUT_SHAPES, room.shape) : ""],
            [
              "Devorlar (uzunlik / balandlik)",
              walls
                .map((w) => `${w.letter} ${w.length ?? "?"}/${w.height ?? "?"}`)
                .join(" · "),
            ],
            [
              "O'lchov",
              survey.measured_at
                ? `${survey.measured_at}${survey.measured_by ? ` — ${survey.measured_by}` : ""}`
                : "",
            ],
            [
              "Buyurtma bo'yicha",
              ORDER_SERVICES.filter((s) => survey[s.key])
                .map((s) => s.label)
                .join(", "),
            ],
          ]}
        />
      </Section>

      <Section title="Material">
        <Facts
          items={[
            ["Korpus", labelsOf(CORPUS_MATERIALS, room.corpus_materials)],
            ["Korpus rangi", room.corpus_color ?? ""],
            [
              "Qalinligi",
              room.corpus_thickness
                ? labelOf(CORPUS_THICKNESS, room.corpus_thickness)
                : "",
            ],
            ["Korpus izohi", room.corpus_note ?? ""],
            ["Fasad", labelsOf(FACADE_MATERIALS, room.facade_materials)],
            ["Fasad rangi", room.facade_color ?? ""],
            [
              "Stol usti",
              room.countertop ? labelOf(COUNTERTOPS, room.countertop) : "",
            ],
            ["Fasad izohi", room.facade_note ?? ""],
            [
              "Furnitura",
              room.hardware_level
                ? labelOf(HARDWARE_LEVELS, room.hardware_level)
                : "",
            ],
          ]}
        />
      </Section>

      <Section title="Mebel turi va xizmatlar">
        <Facts
          items={[
            [
              "Mebel turi",
              [
                labelsOf(FURNITURE_TYPES, room.furniture_types),
                room.furniture_other,
              ]
                .filter(Boolean)
                .join(", "),
            ],
            [
              "Qo'shimcha xizmat",
              labelsOf(EXTRA_SERVICES, room.extra_services),
            ],
            ["Mijoz izohi", room.note ?? ""],
          ]}
        />
      </Section>
    </div>
  )
}
