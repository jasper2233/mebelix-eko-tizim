/** Bazis modelining brauzerdagi ko'rinishi.
 *
 * Shakl backenddagi `services/bazis/viewer.py` bilan QO'LDA oynalangan —
 * kalitlar qisqa (`p`, `q`, `o`), chunki 268 panelli mahsulotda uzun nomlar
 * JSON'ni sezilarli kattalashtiradi, sahifa esa telefonda ochiladi.
 */

import { ORDER_PREFIX } from "@/lib/mes"
import { MAT_RANG, MAT_TEX } from "./matRang.gen"

/** Faqat shu versiyadagi model chiziladi (`viewer.py: VERSION`). JSON yuklashda
 * bir marta yoziladi, ya'ni shakli o'zgarsa eski fayl diskda qoladi — uni
 * yangi kod bilan chizish noto'g'ri geometriya berardi. */
export const MODEL_VERSIYA = 2

export type BazisPanel = {
  /** Detal kodi (`01_005`) — MESdagi `Part.code` ning aynan o'zi. Bo'sh bo'lishi mumkin. */
  id: string
  /** Detal nomi (`Tom`, `Fasad`) */
  n: string
  /** `mats` massividagi material indeksi */
  m: number
  /** Qalinlik, mm */
  t: number
  /** Gabarit [eni, bo'yi], mm */
  s: [number, number]
  /** Mahsulot ichidagi joylashuvi */
  p: [number, number, number]
  /** Burilish kvaternioni */
  q: [number, number, number, number]
  /** Eshik/tortma OCHILGAN holatdagi joylashuv va burilish. Faqat
   * harakatlanadigan panelda bo'ladi (2285 dan 570 tasi) — qolganida yo'q. */
  po?: [number, number, number]
  qo?: [number, number, number, number]
  /** Harakat birligi: bitta eshik yoki tortmaning barcha panellari (tortma —
   * fasad + quti, 5 panel). Faqat harakatlanadigan panelda. */
  g?: number
  /** Tashqi chegara, panelning o'z tekisligida (uchlari bo'yicha ulangan halqa) */
  o: [number, number][]
  /** Chiziq/yoydan chizilgan ichki kesmalar (rakovina, plita teshigi) */
  h?: [number, number][][]
  /** Aylana kesmalar `[cx, cy, r]` — rozetka, kabel teshigi */
  c?: [number, number, number][]
  /** Konturning O'ZI aylana (yumaloq javon): `o` — taqribiy ko'pburchak. */
  rd?: 1
  /** Profil uchini kesuvchi tekisliklar `[nx, ny, nz, d]`, o'z fazosida:
   * `n·p + d >= 0` qoladi (45° li ramka burchaklari). */
  cp?: [number, number, number, number][]
  /** Tekstura tolasi kontur X bo'ylab (Bazis `TexDir = 1`); yo'q bo'lsa — Y bo'ylab */
  r?: 1
}

/** Furnitura/texnika geometriyasining bitta materialli qismi:
 * `[material, uchlar xyz..., normallar xyz..., uchburchak indekslari...]`. */
export type MeshQism = [number, number[], number[], number[]]

/** Furnitura nusxasi — tutqich, oyoq, ilgak, vityajka, varochniy panel.
 * Detal EMAS: kodi yo'q, bosilmaydi va qidiruvga kirmaydi. */
export type Furnitura = {
  /** `meshes` dagi indeks — bir xil tutqich 40 marta takrorlansa ham bir marta */
  k: number
  n: string
  p: [number, number, number]
  q: [number, number, number, number]
  /** Eshikdagi tutqich eshik bilan birga ochiladi (birligi ham o'shaniki) */
  po?: [number, number, number]
  qo?: [number, number, number, number]
  g?: number
}

/** Modelda umuman ochiladigan detal bormi — boshqaruvda «Ochiq» bo'lishi shundan. */
export const hasOpenState = (model: BazisModel): boolean =>
  model.panels.some((p) => p.po !== undefined)

/** Panel qaysi harakat birligida — birlik panellari DOIM birga ochiladi, aks
 * holda tortma harakat paytida bo'laklarga ajralardi. Harakatni o'zi bilan
 * taxmin qilib bo'lmaydi: 460 faylda birliklarning 37% i boshqasi bilan AYNAN
 * bir xil harakatlanadi (bir ilgak chizig'idagi ustma-ust eshiklar). Harakatsiz
 * panelda `null`; `g` siz panel o'zi birlik (manfiy — `g` bilan to'qnashmaydi). */
export const harakatBirligi = (
  p: { po?: unknown; g?: number },
  i: number,
): number | null => (p.po === undefined ? null : (p.g ?? -1 - i))

/** Harakatlanadigan narsalar sahnadagi TARTIBDA: avval panellar, keyin
 * furnitura. Sahna ham, boshqaruv ham birlik raqamini shundan oladi — `g` siz
 * nusxaning zaxira raqami indeksga bog'liq, ya'ni tartib bir xil bo'lishi shart. */
export const harakatElementlari = (model: BazisModel) => [
  ...model.panels,
  ...(model.furn ?? []),
]

/** Bazischi qo'ygan o'lcham (`Размер`) — mahsulot fazosida, yopiq holatda, mm.
 * Chizig'i `a`/`b` dan `o` vektoricha surilgan (Bazisdagidek tashqariga). */
export type BazisOlcham = {
  v: number
  a: [number, number, number]
  b: [number, number, number]
  o: [number, number, number]
  /** Eshik/tortma yig'masi ichidagisi — o'sha birlik ochiq bo'lsa chizilmaydi */
  g?: number
}

export type BazisModel = {
  v: number
  code: string
  name: string
  mats: string[]
  panels: BazisPanel[]
  meshes?: MeshQism[][]
  furn?: Furnitura[]
  /** Bazischining o'lchamlari; eski modelda yo'q (2-bosqichdan oldin yuklangan) */
  d?: BazisOlcham[]
}

/** `q` kvaternion bilan burilgan `v` (three.js siz: sarlavha sahnadan oldin chiziladi). */
const buril = (
  [x, y, z]: [number, number, number],
  [qx, qy, qz, qw]: [number, number, number, number],
): [number, number, number] => {
  const tx = 2 * (qy * z - qz * y)
  const ty = 2 * (qz * x - qx * z)
  const tz = 2 * (qx * y - qy * x)
  return [
    x + qw * tx + (qy * tz - qz * ty),
    y + qw * ty + (qz * tx - qx * tz),
    z + qw * tz + (qx * ty - qy * tx),
  ]
}

/** O'qlarga tekislangan quti `[kam, kop]` — mahsulot fazosida, yopiq holatda */
type Quti = [number[], number[]]

/** Mahalliy nuqtalar `q` bilan burilib `p` ga surilgandagi quti */
const qutiga = (
  uchlar: [number, number, number][],
  p: [number, number, number],
  q: [number, number, number, number],
): Quti => {
  const kam = [Infinity, Infinity, Infinity]
  const kop = [-Infinity, -Infinity, -Infinity]
  for (const u of uchlar) {
    const b = buril(u, q)
    for (let k = 0; k < 3; k++) {
      kam[k] = Math.min(kam[k], p[k] + b[k])
      kop[k] = Math.max(kop[k], p[k] + b[k])
    }
  }
  return [kam, kop]
}

/** Panel qutisi. Konturi yo'q panel sahnada markazlashgan quti (`BoxGeometry`) */
const panelQutisi = (p: BazisPanel): Quti => {
  const [x0, x1, y0, y1, z0, z1] =
    p.o.length >= 3
      ? [
          Math.min(...p.o.map((v) => v[0])),
          Math.max(...p.o.map((v) => v[0])),
          Math.min(...p.o.map((v) => v[1])),
          Math.max(...p.o.map((v) => v[1])),
          0,
          p.t,
        ]
      : [-p.s[0] / 2, p.s[0] / 2, -p.s[1] / 2, p.s[1] / 2, -p.t / 2, p.t / 2]
  const uchlar: [number, number, number][] = []
  for (const x of [x0, x1])
    for (const y of [y0, y1]) for (const z of [z0, z1]) uchlar.push([x, y, z])
  return qutiga(uchlar, p.p, p.q)
}

/** Mahsulot gabariti `[eni, bo'yi, chuqurligi]`, mm — yopiq holatda, faqat
 * panellar bo'yicha. Xona yuzasi (devor, pol) va `zamena` qatlami kirmaydi:
 * 4.2 m li devor bilan oshxona gabariti devorniki bo'lib qolardi. Furnitura
 * ham kirmaydi — tutqich chuqurlikka 30 mm qo'shib, sexdagi o'lchamdan
 * farq qilardi. Bazis o'qlari: X eni, Y bo'yi (tepa), Z chuqurligi. */
export const gabarit = (model: BazisModel): [number, number, number] => {
  const kam = [Infinity, Infinity, Infinity]
  const kop = [-Infinity, -Infinity, -Infinity]
  for (const p of model.panels) {
    if (mebelEmas(model.mats[p.m] ?? "")) continue
    const [a, b] = panelQutisi(p)
    for (let k = 0; k < 3; k++) {
      kam[k] = Math.min(kam[k], a[k])
      kop[k] = Math.max(kop[k], b[k])
    }
  }
  return [0, 1, 2].map((k) =>
    kop[k] > kam[k] ? Math.round(kop[k] - kam[k]) : 0,
  ) as [number, number, number]
}

/** Gabarit o'lchami chiziladigan HAQIQIY qirra: o'qqa parallel chiziq, uning
 * ikki boshqa koordinatasi `[u, v]` (o'qlar tartibida: X uchun Y va Z). */
export type GabaritQirrasi = [number, number] | null

/** Har o'q (X, Y, Z) va har chorak uchun gabarit o'lchami chiziladigan
 * HAQIQIY qirra. Chorak — `(u > markaz ? 1 : 0) + (v > markaz ? 2 : 0)`.
 *
 * Gabarit qutisining qirrasi mahsulotda bo'lishi shart emas: U shaklli
 * oshxonada old qirralar xona o'rtasida havoda (`05 Kuxniya`: X bo'ylab old
 * tepa qirraning 4% ida mebel bor), ramkali shkafda chuqurlik qirralari 3% da
 * (`01 shkaf`: 16 mm li old ramka qutini 160 mm kengaytiradi). U yerga
 * chizilgan o'lcham "fazoda osilib" turardi — egasi ko'rib aytdi; Baymard
 * tadqiqoti ham har o'lchamni mahsulotning o'zidagi joyiga bog'lashni talab
 * qiladi. Shuning uchun har chorakda panellar bo'ylab deyarli BUTUN uzunlikka
 * (80%, ikki uchi bilan) yotgan eng TASHQI chiziq qidiriladi — oddiy qutisimon
 * mebelda u aynan quti qirrasi. Topilmasa `null` — u chorakka chizilmaydi. */
export const gabaritQirralari = (model: BazisModel): GabaritQirrasi[][] => {
  const qutilar = model.panels
    .filter((p) => !mebelEmas(model.mats[p.m] ?? ""))
    .map(panelQutisi)
  if (!qutilar.length) return [[], [], []]
  const kam = [0, 1, 2].map((k) => Math.min(...qutilar.map((q) => q[0][k])))
  const kop = [0, 1, 2].map((k) => Math.max(...qutilar.map((q) => q[1][k])))
  // Tegish chegarasi, birlashtiriladigan tirqish va uchlaridagi yo'l qo'yiladigan
  // kemtik — 22 namunada tanlangan: 3/30 mm da 264 chorakdan 148 tasida chiziq
  // topilardi, qolganlarining ko'pi 94-99% qamrovli (`05 Kuxniya` yon qatori
  // stoleshnitsa chiqib turgani uchun gabaritdan 70 mm qisqa); 30/150 mm va
  // 80% da 178 tasi — qolganlari haqiqatan bo'sh (U oshxonaning ochiq old tomoni)
  const TEG = 30
  const TIRQISH = 150
  const QAMROV = 0.8
  return [0, 1, 2].map((ox) => {
    const [u, v] = [0, 1, 2].filter((k) => k !== ox)
    const uzun = kop[ox] - kam[ox]
    const mu = (kam[u] + kop[u]) / 2
    const mv = (kam[v] + kop[v]) / 2
    const yu = Math.max((kop[u] - kam[u]) / 2, 1)
    const yv = Math.max((kop[v] - kam[v]) / 2, 1)
    const eng: { ball: number; q: GabaritQirrasi }[] = [0, 1, 2, 3].map(() => ({
      ball: Number.NEGATIVE_INFINITY,
      q: null,
    }))
    const korilgan = new Set<string>()
    for (const [a, b] of qutilar)
      for (const cu of [a[u], b[u]])
        for (const cv of [a[v], b[v]]) {
          const kalit = `${Math.round(cu)}:${Math.round(cv)}`
          if (korilgan.has(kalit) || cu === mu || cv === mv) continue
          korilgan.add(kalit)
          const chorak = (cu > mu ? 1 : 0) + (cv > mv ? 2 : 0)
          const ball = Math.abs(cu - mu) / yu + Math.abs(cv - mv) / yv
          if (ball <= eng[chorak].ball) continue
          // Shu chiziqqa tegadigan panellarning o'q bo'ylab oraliqlari
          const oraliq = qutilar
            .filter(
              ([c, d]) =>
                c[u] - TEG <= cu &&
                cu <= d[u] + TEG &&
                c[v] - TEG <= cv &&
                cv <= d[v] + TEG,
            )
            .map(([c, d]) => [c[ox], d[ox]])
            .sort((p, q) => p[0] - q[0])
          let qamrov = 0
          let bosh = Number.NaN
          let oxir = Number.NaN
          for (const [p, q] of oraliq) {
            if (Number.isNaN(bosh)) {
              bosh = p
              oxir = q
            } else if (p <= oxir + TIRQISH) oxir = Math.max(oxir, q)
            else {
              qamrov += oxir - bosh
              bosh = p
              oxir = q
            }
          }
          if (!Number.isNaN(bosh)) qamrov += oxir - bosh
          const uchlari =
            oraliq.length > 0 &&
            oraliq[0][0] <= kam[ox] + TIRQISH &&
            Math.max(...oraliq.map((o) => o[1])) >= kop[ox] - TIRQISH
          if (uchlari && qamrov >= QAMROV * uzun)
            eng[chorak] = { ball, q: [cu, cv] }
        }
    return eng.map((e) => e.q)
  })
}

/** Modul — bitta shkaf yoki blok: detal kodining birinchi bo'lagi (`13_005` →
 * `13`), Bazis yig'masidagi blok raqami. 22 namunada 231 modul; ularning 2143
 * juftidan 47 tasi (2.2%) bir-biriga 10% dan ko'p kirib turadi — amalda
 * alohida qutilar. */
export type Modul = {
  kod: string
  /** `panels` indekslari (xona yuzasi va `zamena` siz) */
  panellar: number[]
  /** `[eni, bo'yi, chuqurligi]`, mm — yopiq holatda */
  olcham: [number, number, number]
}

export const modulKodi = (p: BazisPanel): string | null => {
  const i = p.id.indexOf("_")
  return i > 0 ? p.id.slice(0, i) : null
}

/** Mahsulot modullari (SHKAF va bloklar) — kamida IKKITASI bo'lsa (bitta
 * modulli tumbada modul o'lchami gabaritning o'zi, 22 namunadan 6 tasi).
 * Kirmaydi: `00` guruhi (stoleshnitsa, tsokol — butun mahsulot bo'ylab),
 * kodsiz panellar (22 namunada 6.9%) va quti bo'lmagan guruhlar — 4 tadan kam
 * panelli (planka `pl`, karniz `Qosh`, tsokol `sokl`: 22 namunada 26 tasi 2-3
 * panelli) yoki yupqa (60 mm dan: anteresol taxtasi, LED profil, ko'zgu) yoki
 * ikki o'lchami 150 mm dan kichik. "80 mm" li planka o'lchami shovqin. */
export const modullar = (model: BazisModel): Map<string, Modul> => {
  const guruh = new Map<string, number[]>()
  model.panels.forEach((p, i) => {
    if (mebelEmas(model.mats[p.m] ?? "")) return
    const kod = modulKodi(p)
    if (!kod || kod === "00") return
    const bor = guruh.get(kod)
    if (bor) bor.push(i)
    else guruh.set(kod, [i])
  })
  const natija = new Map<string, Modul>()
  for (const [kod, panellar] of guruh) {
    const qutilar = panellar.map((i) => panelQutisi(model.panels[i]))
    const olcham = [0, 1, 2].map((k) =>
      Math.round(
        Math.max(...qutilar.map((q) => q[1][k])) -
          Math.min(...qutilar.map((q) => q[0][k])),
      ),
    ) as [number, number, number]
    const tartib = [...olcham].sort((a, b) => a - b)
    if (panellar.length < 4 || tartib[0] < 60 || tartib[1] < 150) continue
    natija.set(kod, { kod, panellar, olcham })
  }
  return natija.size >= 2 ? natija : new Map()
}

/** Nomida fasad — harakatsiz to'ldiruvchi va burchak fasadlari (22 namunada 20 ta) */
const FASAD_NOMI = /fasad|фасад/i
/** Fasadga tegib turgan shu o'lchamgacha furnitura — fasadniki (ilgak tanasi
 * 70, planka 50, qulf 50-80, ekssentrik 10 mm). Undan kattasi — ichki
 * mexanizm: yo'naltiruvchi 400-450, vityajka 600, `KARGO` 440-480 mm. */
const FASAD_FURNITURASI = 150

/** «Ichki» ko'rinishda KONTURGA aylanadiganlar — `harakatElementlari`
 * indekslari (avval panellar, keyin furnitura). Nomdan emas, HARAKATDAN —
 * bazischi nomni erkin yozadi (`Fasad`, `1-8 Фасад`, `Двер левая`):
 * * eshik birligi (burilib ochiladi) — butunlay: fasad, shisha, profil,
 *   tutqich, ilgak kosasi;
 * * surma (kupe) eshik birligi — butunlay;
 * * tortma birligi (suriladi) — faqat OLD paneli (harakatga tik, eng oldindagi)
 *   va unga o'rnatilgan furnitura: qutisi va relsi ko'rinib qoladi — usta
 *   aynan shularni o'rnatadi;
 * * harakatsiz, nomida «fasad»;
 * * konturga aylangan varaqqa tegib turgan MAYDA furnitura (`FASAD_FURNITURASI`)
 *   — ilgak tanasi va plankasi, qulf, ekssentrik: ular harakat birligiga
 *   kirmaydi (ilgak tanasi yon devorda qoladi), lekin fasadniki. 22 namunada
 *   fasadga tegadigan 1268 furnituradan 571 tasi ko'rinib qolardi, 525 tasi ilgak.
 * Varag'i yo'q birlik (pantograf, tortib chiqariladigan shtanga) — mexanizm,
 * fasad emas. */
export const fasadlar = (model: BazisModel): Set<number> => {
  const el = harakatElementlari(model)
  const birliklar = new Map<number, number[]>()
  el.forEach((e, i) => {
    const b = harakatBirligi(e, i)
    if (b !== null) birliklar.set(b, [...(birliklar.get(b) ?? []), i])
  })
  const nuqta = (a: number[], b: number[]) =>
    a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
  const natija = new Set<number>()
  for (const idx of birliklar.values()) {
    const panellar = idx.filter((i) => i < model.panels.length)
    if (!panellar.length) continue
    const p0 = model.panels[panellar[0]]
    if (!p0.po || !p0.qo) continue
    const q = p0.q
    const qo = p0.qo
    const cos = Math.abs(
      q[0] * qo[0] + q[1] * qo[1] + q[2] * qo[2] + q[3] * qo[3],
    )
    // 1° dan ko'p burilsa — eshik
    if (cos < Math.cos((0.5 * Math.PI) / 180)) {
      for (const i of idx) natija.add(i)
      continue
    }
    const d = [0, 1, 2].map((k) => (p0.po as number[])[k] - p0.p[k])
    const uzun = Math.hypot(d[0], d[1], d[2])
    if (uzun < 1) continue
    const yon = d.map((v) => v / uzun)
    // Faqat VARAQ: qalinligi eni va bo'yidan kichik. Profil ham panel bo'lib
    // keladi, `t` si esa uzunligi (`Профиль1` 9x33, t=383) — tortib chiqariladigan
    // shtanga birligida u "harakatga tik old panel" bo'lib qolardi (22 namunada
    // 60 ta birlik). 0 mm `zamena` qatlami ham old panel emas.
    const varaq = panellar.filter((i) => {
      const p = model.panels[i]
      return p.t >= 1 && p.t < Math.min(p.s[0], p.s[1])
    })
    const normal = (i: number) => buril([0, 0, 1], model.panels[i].q)
    const tikmi = (i: number) => Math.abs(nuqta(normal(i), yon))
    const eng = (tanla: (i: number) => boolean) =>
      Math.max(
        0,
        ...varaq
          .filter(tanla)
          .map((i) => model.panels[i].s[0] * model.panels[i].s[1]),
      )
    // Surma (kupe) eshik: tabaqasi TIK turadi, harakat bo'ylab yotadi va
    // harakatga qaragan varaqdan ko'p barobar katta (odatda bunday varaq yo'q).
    // Tortmada tubi old paneldan 2-4 barobar katta xolos, u yotiq ham — tik
    // shart tortib chiqariladigan javonni (old paneli yo'q) eshik qilmaydi.
    if (
      eng((i) => tikmi(i) < 0.3 && Math.abs(normal(i)[1]) < 0.3) >
      5 * eng((i) => tikmi(i) > 0.9)
    ) {
      for (const i of idx) natija.add(i)
      continue
    }
    let old = -1
    let oldM = Number.NEGATIVE_INFINITY
    for (const i of varaq) {
      const p = model.panels[i]
      if (tikmi(i) < 0.9) continue
      const xs = p.o.map((v) => v[0])
      const ys = p.o.map((v) => v[1])
      const yerli: [number, number, number] = p.o.length
        ? [
            (Math.min(...xs) + Math.max(...xs)) / 2,
            (Math.min(...ys) + Math.max(...ys)) / 2,
            p.t / 2,
          ]
        : [0, 0, 0]
      const b = buril(yerli, p.q)
      const m = nuqta([p.p[0] + b[0], p.p[1] + b[1], p.p[2] + b[2]], yon)
      if (m > oldM) {
        old = i
        oldM = m
      }
    }
    if (old < 0) continue
    natija.add(old)
    // Old panelga TASHQARIDAN o'rnatilgani (tutqich): boshi old panelning
    // markaz tekisligidan oldinda (22 namunada tutqich +7 mm, ichkaridagi
    // `KARGO` mexanizmi −9 mm — u ko'rinib qolishi kerak, usta uni o'rnatadi)
    for (const i of idx)
      if (i >= model.panels.length && nuqta(el[i].p, yon) >= oldM) natija.add(i)
  }
  model.panels.forEach((p, i) => {
    if (p.po === undefined && FASAD_NOMI.test(p.n)) natija.add(i)
  })
  const fasadQutilari = [...natija]
    .filter((i) => i < model.panels.length && model.panels[i].t > 0)
    .map((i) => panelQutisi(model.panels[i]))
  const tegadi = ([a, b]: Quti) =>
    fasadQutilari.some(([c, d]) =>
      [0, 1, 2].every((k) => a[k] <= d[k] + 2 && c[k] <= b[k] + 2),
    )
  // Furnitura geometriyasi bir necha nusxada — mahalliy uchlari bir marta
  const uchlar = new Map<number, [number, number, number][]>()
  const uchlari = (k: number) => {
    let u = uchlar.get(k)
    if (!u) {
      u = []
      for (const [, v] of model.meshes?.[k] ?? [])
        for (let j = 0; j + 2 < v.length; j += 3)
          u.push([v[j], v[j + 1], v[j + 2]])
      uchlar.set(k, u)
    }
    return u
  }
  model.furn?.forEach((f, j) => {
    const i = model.panels.length + j
    if (natija.has(i) || !uchlari(f.k).length) return
    const quti = qutiga(uchlari(f.k), f.p, f.q)
    const eng = Math.max(...[0, 1, 2].map((k) => quti[1][k] - quti[0][k]))
    if (eng <= FASAD_FURNITURASI && tegadi(quti)) natija.add(i)
  })
  return natija
}

/** Xona yuzasi — devor, pol, shift. MEBEL EMAS: bazischi mahsulot qayerga
 * qo'yilishini ko'rsatish uchun qo'shadi.
 *
 * 460 ta haqiqiy modelda o'lchandi: 107 tasida (23%) xona yuzasi bor va u
 * yuzaning 50-100% ini egallaydi — 100 mm qalin, berk qutini yasab, mebelni
 * butunlay yopib qo'yadi. Qoida 140 ta material nomidan `Devor` (171) va `Pol`
 * (59) ni tutadi, yolg'on ijobiysi yo'q. `pol` so'z sifatida: `polka` (javon)
 * bunga tushmaydi. Kafel bu yerda EMAS — `DEVOR_QOPLAMASI`. */
export const XONA_YUZASI =
  /devor|(^|[^a-z])pol([^a-z]|$)|стен|потол|wall|floor/i

/** Devor qoplamasi — kafel (fartuk): stoleshnitsa bilan ustki shkaflar
 * orasidagi 10 mm li panel (`KAFEL 300x60 mm`, 460 faylda 99 marta). Ilgari
 * xona yuzasiga qo'shilgan edi va 16% shaffof, teksturasiz, BOSILMAS turardi —
 * egasi: "kafel yoki nimadur bo'ladi… ustiga bosganda o'lchamlarini bilib
 * bo'lmaydi". U berk quti yasamaydi, detal kodi bor (`00_004`) — oddiy panel
 * kabi chiziladi (katalog teksturasi bilan) va bosiladi. Faqat mebel o'lchamiga
 * kirmaydi: oshxona chuqurligi devor qoplamasi bilan 10 mm oshib ketardi. */
export const DEVOR_QOPLAMASI = /kafel|кафел/i

/** Mebel gabaritiga, haqiqiy qirralar va modullarga kirmaydi: xona yuzasi, devor
 * qoplamasi va ko'rinmas `zamena` qatlami */
export const mebelEmas = (nom: string): boolean =>
  XONA_YUZASI.test(nom) ||
  DEVOR_QOPLAMASI.test(nom) ||
  maxsusYuza(nom) === "zamena"

/** Material NOMIDAN ko'rinish — KATALOGDA topilmagan nomlar uchun ZAXIRA yo'l.
 * Birinchi navbat `MAT_RANG` da (`matRang.gen.ts`, ishlatilishning 74% i).
 *
 * Kalit so'zlar 437 ta haqiqiy buyurtmadagi
 * 162 material nomidan olingan (85 753 ishlatilish), o'ylab topilmagan:
 * `kromka PVC 06-19 oq`, `LDSP DUB VATAN TEKSTURA`, `AKRIL KASHMIR GLYANETS`.
 *
 * Nega nom bo'yicha, indeks bo'yicha emas: ilgari rang `mats` massividagi
 * o'rindan olinardi, ya'ni AYNAN BIR XIL material bir mahsulotda bej,
 * boshqasida kulrang chiqardi — bitta buyurtmaning ikki mahsulotini
 * solishtirgan usta chalg'irdi. */
const RANGLAR: [RegExp, string][] = [
  // Xona yuzalari BIRINCHI: ular mebel emas va zaxira rangda «yong'oq devor»
  // bo'lib chiqardi.
  [XONA_YUZASI, "#d3d6da"],
  [/экран|ekran/i, "#15171a"],
  // Varochniy panel — qora shisha-keramika (460 faylda 31 panel `варочная`)
  [/варочн|varoch/i, "#1d1f22"],
  [/oyna|shisha|stek|стек|зерк|kozgu|ko'zgu/i, "#9fc2d6"],
  [/qora|чёрн|черн|black/i, "#2a2a2c"],
  // Furnitura qismlari (`FurnList` meshi): `GTV Nikel plated`, `Boyard
  // Нержавеющая сталь`, `Хром матовый` — metall; `kul rang` — kulrang.
  [
    /metalik|metlik|серебр|silver|nikel|никел|xrom|хром|chrome|сталь|нерж|inox|steel|alumin|ал+юмин|\ball?u\b/i,
    "#b9bdc2",
  ],
  [/antrasit|anthracite|антрацит/i, "#3b3e43"],
  [/jigar/i, "#6d5647"],
  // `LDSP dub beliy` — OQARTIRILGAN eman: Bazis yozuvidagi `dub beliy.jpg` o'rtachasi.
  // Ilgari `dub` birinchi tushib, 68 panel jigarrang chiqardi (ΔE 37).
  [/dub\s*beli|дуб\s*бел/i, "#e3dfd5"],
  // Kirillchasi ham: Bazis nomni ruscha yozishi mumkin (`Дубь Честерфильд` —
  // 460 faylda 304 panel, `Мокко` — 22) va ular betaraf kulrangga tushib,
  // yog'och shkaf butunlay kulrang chiqardi.
  [/mokriy|mokko|мокко|wenge|venge|tyomniy|темн/i, "#6d5647"],
  [/dub|дуб|votan|vatan|oak|орех|yong'oq/i, "#b98f5e"],
  [/sasna|asina|sosna|pine|olxa/i, "#cfa878"],
  [/kashmir|кашемир|krem|беж|bej|cream/i, "#d9c9ad"],
  [/zolota|tilla|gold|золот/i, "#c4a24a"],
  [/kaspiy|grafit|seriy|серый|grey|gray|kul\s*rang/i, "#9aa0a6"],
  [/oq|beli|бел|white/i, "#f2f1ee"],
]

/** Kalitga tushmagan nom uchun BETARAF ohang — ataylab yog'och ham, bej ham
 * emas. Ilgari zaxira palitrasida bej bor edi va `zamena material` (jami
 * ishlatilishning 3.9% i) kashmir bilan deyarli bir xil chiqib, tumbaning
 * ikki eshigi qolganidan ajralmay qolgan edi. Noma'lum material noma'lum
 * bo'lib ko'rinishi kerak, oilaga taqlid qilmasligi kerak. */
const ZAXIRA = [
  "#cfd2d6",
  "#c2c5c9",
  "#d5d2cd",
  "#b8bcc1",
  "#c9c5c0",
  "#dbd8d4",
]

const hash = (s: string): number => {
  let h = 0
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0
  return Math.abs(h)
}

/** Bir xil KALITGA tushgan ikki materialni ajratib turish uchun nozik
 * tafovut: yorqinlik ±7%, ohang ±8°. Nomdan olingani uchun barqaror.
 *
 * Kerak, chunki `LDSP KASHMIR SHAGREN` va `zamena material` bitta oilaga
 * tushib, tumbaning ikki eshigi qolganidan farq qilmay qolgan edi — usta
 * ularning BOSHQA material ekanini ko'rmasdi. Tafovut kichik: oila saqlanadi
 * («dub» baribir yog'och bo'lib ko'rinadi), lekin panellar ajraladi. */
const tafovut = (hex: string, nom: string): string => {
  const n = Number.parseInt(hex.slice(1), 16)
  const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255]
  const h = hash(nom)
  // -1..+1 oralig'ida ikki mustaqil kichik siljish
  const yorug = (((h % 101) / 50 - 1) * 7) / 100
  const ohang = ((((h / 101) | 0) % 101) / 50 - 1) * 8
  const o = [r, g, b].map((c) => c / 255)
  const mx = Math.max(...o)
  const mn = Math.min(...o)
  let H = 0
  const L = Math.min(1, Math.max(0, (mx + mn) / 2 + yorug))
  const S = mx === mn ? 0 : (mx - mn) / (1 - Math.abs(mx + mn - 1))
  if (mx !== mn) {
    const d = mx - mn
    H =
      mx === o[0]
        ? ((o[1] - o[2]) / d + (o[1] < o[2] ? 6 : 0)) * 60
        : mx === o[1]
          ? ((o[2] - o[0]) / d + 2) * 60
          : ((o[0] - o[1]) / d + 4) * 60
  }
  H = (H + ohang + 360) % 360
  const c = (1 - Math.abs(2 * L - 1)) * S
  const x = c * (1 - Math.abs(((H / 60) % 2) - 1))
  const m = L - c / 2
  const t: number[][] = [
    [c, x, 0],
    [x, c, 0],
    [0, c, x],
    [0, x, c],
    [x, 0, c],
    [c, 0, x],
  ]
  const [R, G, B] = t[Math.floor(H / 60) % 6].map((v) =>
    Math.round((v + m) * 255),
  )
  return `#${((R << 16) | (G << 8) | B).toString(16).padStart(6, "0")}`
}

/** Material nomini katalog kaliti holiga keltiradi.
 *
 * `scripts/bazis-material-colors.py: norm()` bilan QO'LDA oynalangan —
 * birini o'zgartirsang ikkinchisini ham, aks holda jadval kaliti mos
 * kelmay qoladi va rang jimgina regexga tushib ketadi.
 *
 * Texnolog Bazisda plita kvadraturasini va yetkazuvchini nomga qo'shadi
 * (`LDSP DUB VOTAN 5.03 kv.  Khatdekor`), katalogda esa `LDSP DUB VATAN`
 * turadi — shu shovqin olib tashlanadi. */
const normMat = (nom: string): string =>
  nom
    .toLowerCase()
    .trim()
    .replace(/\d+[.,]\d+\s*kv\.?/g, " ")
    .replace(/\d{3,4}\s*[xх*]\s*\d{3,4}(\s*[xх*]\s*\d+)?(\s*mm)?/g, " ")
    .replace(/\(\s*\d+\s*mm\s*\)/g, " ")
    .replace(/\b\d+\s*mm\b/g, " ")
    .replace(/khatde[ck]or|kronospan|xitoy|mestniy|местный/g, " ")
    .replace(/\bagt\b|\bbir tomon\b/g, " ")
    .replace(/votan/g, "vatan")
    .replace(/mokrik/g, "mokriy")
    .replace(/beliy?/g, "beli")
    .replace(/tiilla/g, "tilla")
    .replace(/glyans/g, "glyanets")
    .replace(/mativiy/g, "matviy")
    .replace(/[^a-z0-9а-яё ]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()

/** Panel rangi. Katalogdagi HAQIQIY rangga TEGILMAYDI — u tekstura rasmining
 * o'rtachasi yoki katalogda yozilgan rang, ya'ni taxmin emas. Tafovut faqat
 * regex zaxirasiga qo'llanadi: u yerda rang baribir taxminiy va bir kalitga
 * tushgan ikki materialni ajratib turish kerak. Bir xil rang chiqqan ikki
 * dekor rostdan bir xil ko'rinadi — yaltiroqligi `materialRoughness` da. */
export type Tekstura = {
  url: string
  /** Bitta tayl — rasm shu o'lchamdagi yuzani qoplaydi, mm (katalogdagi tayl,
   * rasm tomonlari nisbati bilan) */
  eni: number
  boyi: number
  /** Katalogdagi qo'shimcha burchak, gradus */
  burchak: number
  /** Rasmda tola ENI bo'ylab (yotiq stoleshnitsa fotosi); aks holda bo'yi bo'ylab */
  tolaU: boolean
  /** Shu o'qda rasm chetlari tutashmaydi (oddiy foto) — ko'zgu kabi ulanadi */
  aksU: boolean
  aksV: boolean
}

/** Naqshli materialning teksturasi (yog'och tolasi, marmar, beton) — katalogdan,
 * generatsiya paytida hal qilingan (`MAT_TEX`). Tekis rasmli materialda
 * `undefined`: unga `materialColor` — rasmning o'rtachasi — yetarli. */
export const materialTexture = (nom: string): Tekstura | undefined => {
  const t = MAT_TEX[normMat(nom)]
  return (
    t && {
      url: `/assets/tex/${t[0]}`,
      eni: t[1],
      boyi: t[2],
      burchak: t[3],
      tolaU: t[4] === 1,
      aksU: t[5] === 1,
      aksV: t[6] === 1,
    }
  )
}

export const materialColor = (nom: string): string => {
  const katalog = MAT_RANG[normMat(nom)]
  if (katalog) return katalog
  for (const [naqsh, rang] of RANGLAR)
    if (naqsh.test(nom)) return tafovut(rang, nom)
  return tafovut(ZAXIRA[hash(nom) % ZAXIRA.length], nom)
}

/** Kartochkadagi material nomi — Bazis qo'shadigan shovqinsiz: plita
 * kvadraturasi, formati, qalinligi va yetkazuvchisi. `ЛМДФ (Местный) 2750х1830
 * Дубь Честерфильд 16мм` -> `ЛМДФ Дубь Честерфильд`. Qalinlik va o'lcham
 * kartochkada o'z qatorida turibdi, ya'ni hech narsa yo'qolmaydi.
 *
 * `normMat` bilan birlashtirilmagan: u katalog KALITI (kichik harf, tinishsiz,
 * skript bilan qo'lda oynalangan), bu esa ko'rsatish — asl yozilish qoladi. */
export const materialKorinishi = (nom: string): string =>
  nom
    // `5.03 kv`, `5,796 кв`, `-2.316 kv` — plita kvadraturasi
    .replace(/-?\d+[.,]\d+\s*(kv|кв)\.?/gi, " ")
    // `2750х1830`, `2800*1220*18`, `25×600×3000`, `300x60 mm` — format
    .replace(
      /\d{2,4}\s*[xх*×]\s*\d{2,4}(\s*[xх*×]\s*\d+)?(\s*(mm|мм|sm|см))?/gi,
      " ",
    )
    // `16мм`, `(16 mm)` — qalinlik
    .replace(/\d+([.,]\d+)?\s*(mm|мм)(?![a-zа-яё])/gi, " ")
    .replace(/khatde[ck]or|kronospan|кроношпан|mestniy|местный/gi, " ")
    .replace(/(^|\s)agt(?=\s|$)/gi, " ")
    .replace(/\(\s*\)/g, " ")
    .replace(/\s+/g, " ")
    .trim() || nom

/** Yaltiroqlik ham nomdan: `GLYANETS` yaltiroq, `MATVIY`/`SHAGREN` mat.
 * 437 buyurtmada `glyanets` 10.7%, `matviy` 7.8%, `shagren` 5.1% ishlatilgan. */
export const materialRoughness = (nom: string): number => {
  const yuza = maxsusYuza(nom)
  if (yuza === "kozgu") return 0.06
  if (yuza === "ekran") return 0.22
  if (yuza === "shisha") return 0.12
  if (/glyanets|glyans|глянц|gloss/i.test(nom)) return 0.28
  if (/matviy|мат|shagren|шагрен/i.test(nom)) return 0.85
  return 0.7
}

/** `002` va `2` — bitta raqam: usta boshidagi nollarni termasligi mumkin. */
const tengSon = (a: string, b: string): boolean =>
  a === b || (/^\d+$/.test(a) && /^\d+$/.test(b) && Number(a) === Number(b))

/** Qidiruv natijasining kuchi: 0 — mos emas, 1 — qisman (tugallanmagan kod yoki
 * nomda), 2 — AYNAN shu detal kodi. */
export type Moslik = 0 | 1 | 2

/** Detalni kod yoki nom bo'yicha topish — yig'uvchi qo'lidagi chekdan o'qiydi.
 *
 * Chekda faqat to'liq Detal ID bosiladi: `{buyurtma}_{mahsulot}_{detal}[-N][_n]`
 * (docs/11, `giblab/models.py: instance_qr`), masalan `B-2026-001_208301_23_002_2`.
 * Usta aynan shuni teradi, shuning uchun buyurtma prefiksi va mahsulot kodi olib
 * tashlanadi; mahsulot kodi bo'lsa (ya'ni to'liq ID terilgan) detal kodidan
 * keyin faqat `-N` takror va `_n` nusxa raqami qolishi mumkin.
 *
 * Solishtirish `_` bo'laklari bo'yicha, SATR ICHIDA emas: ilgari `03_002`
 * normallashib `3_2` bo'lardi va `23_002`, `13_002` ham "topilardi". Oxirgi
 * bo'lak prefiks bo'lishi mumkin — `23_0` terilayotganda ro'yxat bo'sh qolmasin. */
export const matchPanel = (
  panel: BazisPanel,
  query: string,
  productCode: string,
): Moslik => {
  const xom = query.trim().toLowerCase()
  if (!xom) return 0
  const id = panel.id.toLowerCase()
  if (id) {
    let q = xom.replace(ORDER_PREFIX, "")
    const mk = productCode.trim().toLowerCase()
    const toliqId = mk !== "" && q.startsWith(`${mk}_`)
    if (toliqId) q = q.slice(mk.length + 1)
    const it = id.split("_")
    const qt = q.split("_")
    if (toliqId) {
      const bosh = qt.slice(0, it.length)
      bosh[it.length - 1] = (bosh[it.length - 1] ?? "").replace(/-\d+$/, "")
      const dum = qt.slice(it.length)
      if (
        qt.length >= it.length &&
        bosh.every((t, i) => tengSon(t, it[i])) &&
        dum.length <= 1 &&
        dum.every((t) => /^\d+$/.test(t))
      )
        return 2
    } else if (q && qt.length <= it.length) {
      const oxirgi = qt.length - 1
      if (qt.slice(0, oxirgi).every((t, i) => tengSon(t, it[i]))) {
        if (qt.length === it.length && tengSon(qt[oxirgi], it[oxirgi])) return 2
        if (it[oxirgi].startsWith(qt[oxirgi])) return 1
      }
    }
  }
  return panel.n.toLowerCase().includes(xom) ? 1 : 0
}

/** Oyna, shisha va ekran — ular ORQASI ko'rinishi kerak, aks holda model
 * ichidagi javonlar yo'qoladi. Nomlar prodda uchraganidek: rus va o'zbek. */
export type MaxsusYuza = "shisha" | "kozgu" | "ekran" | "zamena"

/** Uch xil yaltiroq yuza, uchalasi uch xil chiziladi:
 * * SHISHA — yarim shaffof: ortidagi javonlar ko'rinib tursin;
 * * KO'ZGU — shaffof EMAS, metall kabi aks ettiradi. Ilgari `Зеркало` shisha
 *   bo'lib shaffof, `Kozgu` esa mat buyum bo'lib chizilardi (54 panel);
 * * EKRAN — televizor ekrani, deyarli qora va yaltiroq. Ilgari u shishalar
 *   qatorida 34% shaffof och-ko'k parda edi — televizor ko'rinmasdi.
 * Katalogda shaffoflik yo'q (`PARAM_7` 240 yozuvning hammasida 0), ya'ni nomdan. */
export const maxsusYuza = (nom: string): MaxsusYuza | undefined => {
  // `zamena material` — fasad USTIGA qo'yiladigan 0 mm li qatlam (460 faylda
  // 3447 panel, 91% i aynan haqiqiy fasad/orqa panel yuzasida yotadi). Bazisda
  // u TO'LIQ SHAFFOF: fayldagi `Mt` yozuvlarining hammasida `Transparency = 1`.
  // Ilgari u 1 mm li kulrang plita bo'lib chizilib, ostidagi haqiqiy fasadni
  // yopardi — fasadlar eskizdagidan boshqa rangda chiqardi.
  if (/zamena|замена/i.test(nom)) return "zamena"
  if (/экран|ekran/i.test(nom)) return "ekran"
  if (/зерк|kozgu|ko['`‘’]?zgu|mirror/i.test(nom)) return "kozgu"
  if (/oyna|shisha|stek|стек|glass/i.test(nom)) return "shisha"
  return undefined
}

/** Haqiqiy metall — furnitura qismlari va alyumin profil (muzlatkich
 * korpusi `ALLU`; `GTV Alu`, `Аллюмин`, `LED profil alumin`, `Steel` — 460
 * faylda shu yozilishlarning hammasi uchraydi). `LDSP METALIK SHAGREN` kabi
 * DEKOR nomi bunga tushmaydi: u metall rangidagi plita, o'zi metall emas. */
export const isMetal = (nom: string): boolean =>
  /xrom|хром|chrome|nikel|никел|сталь|нерж|inox|stainless|steel|\ball?u\b|alyumin|alumin|ал+юмин/i.test(
    nom,
  )
