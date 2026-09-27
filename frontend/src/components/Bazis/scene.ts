/** Bazis modelining three.js sahnasi — Reactdan mustaqil.
 *
 * Komponent faqat ulaydi: sahna, kamera va tanlash mantig'i shu yerda, chunki
 * har kadrda React holatini yangilash telefonda kadr tezligini yo'qotardi.
 *
 * O'lchov birligi — millimetr, Bazisdagidek. Bazisning o'qlari three.js bilan
 * BIR XIL (Y — tepa), shuning uchun hech narsa aylantirilmaydi.
 * Ekstruziya konturdan +Z bo'yicha `Thick` ga: 22 namunadagi 1272 panelda
 * o'lchandi — tegib turgan juftlar 5191 ta, teskari yo'nalishda 1786.
 */

import {
  Box3,
  BoxGeometry,
  BufferGeometry,
  CanvasTexture,
  DirectionalLight,
  DoubleSide,
  EdgesGeometry,
  ExtrudeGeometry,
  Float32BufferAttribute,
  Group,
  LineBasicMaterial,
  LineSegments,
  type Material,
  Matrix4,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
  MirroredRepeatWrapping,
  NeutralToneMapping,
  type Object3D,
  Path,
  PerspectiveCamera,
  PlaneGeometry,
  PMREMGenerator,
  Quaternion,
  Raycaster,
  RepeatWrapping,
  Scene,
  Shape,
  SRGBColorSpace,
  type Texture,
  TextureLoader,
  Vector2,
  Vector3,
  WebGLRenderer,
} from "three"
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js"
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js"
import { type Ilgak, ilgakHolati, ilgakOqi } from "./ilgak"
import {
  type BazisModel,
  type BazisPanel,
  fasadlar,
  type GabaritQirrasi,
  gabarit,
  gabaritQirralari,
  harakatBirligi,
  harakatElementlari,
  isMetal,
  materialColor,
  materialRoughness,
  materialTexture,
  maxsusYuza,
  mebelEmas,
  type Tekstura,
  XONA_YUZASI,
} from "./model"

/** Panelning ko'rinish holati. `kontur` — «Ichki» ko'rinishdagi fasad:
 * yuzasi deyarli yo'q, qirrasi qoladi. `qoshni` — tanlangan detalga tegib
 * turgan panel (u nimaga ulanadi). */
type Holat = "oddiy" | "xira" | "tanlangan" | "topilgan" | "kontur" | "qoshni"

const RANG = {
  qirra: "#44546b",
  tanlangan: "#f0a52f",
  /** Tanlangan detal konturi — oltindan quyuqroq, oq fonda ham ko'rinadi */
  tanlanganQirra: "#a8600a",
  topilgan: "#2f496e",
}

/** Bitta birlikning (eshik, tortma) harakati. */
const HARAKAT_MS = 460
/** Kaskad: birinchi va oxirgi birlik BOSHLANISHI orasidagi vaqt. Birliklar
 * SONIGA bog'liq emas — 104 birlikli modelda ham hammasi ~0.76 s da ochiladi.
 * Birma-bir ochish (har biri 460 ms) 460 faylda o'rtacha 5.5 s, eng uzuni
 * 48 s bo'lardi — holat tugmasi filmga aylanardi. */
const KASKAD_MS = 300

/** O'lcham chizig'ining qirradan uzoqligi, px — qirra o'rtasida, tik o'qning O'Z
 * masshtabi bilan: burchak ostida ikki o'q har xil qisqaradi. Chizmachilikda
 * birinchi qator obyektdan ~4 strelka uzunligida (Cambridge: strelka 3 mm,
 * qator 12 mm); gabarit — tashqi qator, undan ham narida. */
const OLCHAM_CHETI = 24
const GABARIT_CHETI = 32
/** Tor ekranda (telefon portreti) mahsulot kenglikni to'ldiradi va chetdagi
 * yorliq ekrandan chiqib ketadi: har nomzod oxirida shu surilish bilan yana
 * bir bor sinaladi. Sahnada o'lchandi (390 px, 4 model, 15 old ko'rinish):
 * bo'yi 7-8 dan 11-12 ko'rinishda chiziladigan bo'ldi (ilgari, 18 px da, 8-10). */
const TOR_CHETI = 16
/** Uzatma chiziq: obyektdan TIRQISH bilan boshlanadi va o'lcham chizig'idan
 * OSHIB o'tadi, px. Tirqish ~ oshishning yarmi (US amaliyoti 1/16″ va 1/8″),
 * oshish ~ strelka uzunligi (Cambridge 3 mm = 3 mm). */
const TIRQISH = 3
const OSHISH = 6
/** Strelka, px: uzunligi va yarim eni — ~3:1 ga yaqin ingichka uchburchak */
const STRELKA = 8
const STRELKA_ENI = 2
/** Yorliqning chiziq bo'ylab joylari: avval o'rtasi, keyin chetrog'i */
const YORLIQ_JOYI = [0.5, 0.35, 0.65, 0.2, 0.8]

export type PanelHit = { panel: BazisPanel; index: number } | null

export type SceneApi = {
  load: (model: BazisModel) => void
  setSelected: (indexes: number[]) => void
  setFound: (indexes: Set<number>) => void
  /** Ko'rinish holati: qaysi harakat birliklari ochiq (`model.ts:
   * harakatBirligi`) va ajratilganlik. Harakatni sahnaning o'zi o'ynatadi. */
  setPose: (ochiqBirliklar: ReadonlySet<number>, explode: number) => void
  /** Kamerani detalga (barcha nusxalari markaziga) olib boradi */
  focusOn: (indexes: number[]) => void
  /** Orbit markazini mahsulotga qaytaradi (detal tanlovi yopilganda) */
  nishonniQaytar: () => void
  resetView: () => void
  /** Kanvasning pastini egallagan qatlam balandligi (px) — kartochka yoki
   * qidiruv natijalari. Kadr markazi bo'sh joyga suriladi. */
  setPastkiBand: (px: number) => void
  /** O'lcham yorlig'i tushmaydigan qatlamlar, px: yuqorida tugmalar qatori,
   * pastda kartochka + qidiruv. `setPastkiBand` dan farqi — qidiruv maydoni
   * ham kiradi: kadr uni hisobga olmaydi, yorliq esa uning ostida qolardi. */
  setYorliqZona: (ust: number, past: number) => void
  /** «O'lchamlar» tugmasi: gabarit va bazischining o'lchamlari (D2) */
  setOlchamlar: (yoniq: boolean) => void
  /** «Ichki» ko'rinish: fasadlar kontur bo'lib qoladi (`model.ts: fasadlar`) */
  setIchki: (yoniq: boolean) => void
  dispose: () => void
}

export const shapeFor = (panel: BazisPanel): Shape | null => {
  if (panel.o.length < 3) return null
  const shape = new Shape(panel.o.map(([x, y]) => new Vector2(x, y)))
  // Rakovina, plita kabi kesmalar: ilgari tashqi chegaraga qo'shib yuborilib,
  // o'z-o'zini kesadigan shakl berardi (41 305 paneldan 494 tasida kesma bor).
  for (const kesma of panel.h ?? []) {
    shape.holes.push(new Path(kesma.map(([x, y]) => new Vector2(x, y))))
  }
  for (const [cx, cy, r] of panel.c ?? []) {
    const hole = new Path()
    hole.absarc(cx, cy, r, 0, Math.PI * 2, true)
    shape.holes.push(hole)
  }
  return shape
}

/** Profil uchlarini `[nx, ny, nz, d]` tekisliklari bilan kesadi (45° li ramka
 * burchaklari): `n·p + d < 0` tomondagi uch Z bo'ylab tekislikka suriladi.
 * 460 fayldagi hamma tekislikda `nz ≠ 0` (normallar `(±0.7071, 0, ±0.7071)`),
 * ya'ni surish aniq va yon devorlar tekis qoladi. Busiz 163 ta ramka va
 * karniz a'zosining uchlari burchakda ustma-ust chiqardi. */
export const kes = (
  geo: BufferGeometry,
  tekisliklar: [number, number, number, number][],
) => {
  const uch = geo.getAttribute("position")
  for (let i = 0; i < uch.count; i++) {
    const x = uch.getX(i)
    const y = uch.getY(i)
    let z = uch.getZ(i)
    for (const [nx, ny, nz, d] of tekisliklar) {
      if (Math.abs(nz) > 1e-6 && nx * x + ny * y + nz * z + d < 0)
        z = -(nx * x + ny * y + d) / nz
    }
    uch.setZ(i, z)
  }
  uch.needsUpdate = true
  geo.computeVertexNormals()
}

/** Barqaror "tasodif" 0..1 — butun sondan (murmur3 aralashtirgichi): model har
 * ochilganda naqsh bir xil joyda turadi. */
const tasodif = (n: number): number => {
  let h = Math.imul(n ^ 0x5bd1e995, 0x85ebca6b)
  h ^= h >>> 13
  h = Math.imul(h, 0xc2b2ae35)
  h ^= h >>> 16
  return (h >>> 0) / 2 ** 32
}

/** Naqshni panelga joylaydi. Har detal varaqning BOSHQA joyidan kesiladi, rasm
 * esa hamma panelda konturning (0, 0) nuqtasidan boshlanardi — yonma-yon
 * eshiklar aynan bir xil naqshli, nusxa ko'chirilgandek chiqardi. Siljish panel
 * BITTA tayl ichida qoladigan qilib tanlanadi: tayldan kichik detalga tayl
 * chegarasi (ko'zgu chizig'i) tushmaydi. Yuza UV'si — kontur mm da
 * (`ExtrudeGeometry`), tayl o'lchami `teksturaQoy` da. */
export const naqshSiljit = (
  geo: BufferGeometry,
  t: Tekstura,
  burilgan: boolean,
  urug: number,
) => {
  geo.computeBoundingBox()
  const b = geo.boundingBox
  if (!b) return
  // 90° burilganda kontur X rasmning bo'yi (V) bo'ylab ketadi
  const [tx, ty] = burilgan ? [t.boyi, t.eni] : [t.eni, t.boyi]
  const dx = -b.min.x + tasodif(2 * urug) * Math.max(0, tx - b.max.x + b.min.x)
  const dy =
    -b.min.y + tasodif(2 * urug + 1) * Math.max(0, ty - b.max.y + b.min.y)
  const uv = geo.getAttribute("uv")
  for (let i = 0; i < uv.count; i++)
    uv.setXY(i, uv.getX(i) + dx, uv.getY(i) + dy)
}

/** Kontakt soyasi uchun yumshoq dog': markazda quyuq, chetga qarab yo'qoladi.
 *
 * Haqiqiy `shadowMap` emas — 268 panelli mahsulotda u har kadrda ikkinchi
 * o'tish talab qilardi va planshetda kadr tezligini yeb qo'yardi. Vazifasi
 * bitta: mahsulot POLDA turgandek ko'rinsin, havoda suzmasin. */
const shadowTexture = (): CanvasTexture => {
  const N = 256
  const c = document.createElement("canvas")
  c.width = c.height = N
  const ctx = c.getContext("2d")
  if (ctx) {
    const g = ctx.createRadialGradient(N / 2, N / 2, 0, N / 2, N / 2, N / 2)
    g.addColorStop(0, "rgba(36,52,74,0.42)")
    g.addColorStop(0.45, "rgba(36,52,74,0.18)")
    g.addColorStop(1, "rgba(36,52,74,0)")
    ctx.fillStyle = g
    ctx.fillRect(0, 0, N, N)
  }
  return new CanvasTexture(c)
}

export function createScene(
  canvas: HTMLCanvasElement,
  onPick: (hit: PanelHit) => void,
  /** O'lcham yorliqlari qatlami — kanvas ustida, uning o'lchamida */
  qatlam?: HTMLElement,
): SceneApi {
  // `alpha` — fon CSS gradienti bilan beriladi (`ModelViewer`): studiya
  // fonidagi yumshoq o'tish WebGL'da emas, brauzerda tekin chiziladi.
  const renderer = new WebGLRenderer({ canvas, antialias: true, alpha: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  // Khronos "neutral" — aynan mahsulot ko'ruvchilar uchun. ACES kino uchun
  // qilingan: u rang tusini siljitadi va bu yerda oq plita bilan yog'ochni
  // bir-biriga yaqinlashtirib, tanlangan detalning oltin rangini xiralashtirardi.
  renderer.toneMapping = NeutralToneMapping
  renderer.toneMappingExposure = 0.86

  const scene = new Scene()
  // `near` 40 mm: 24 bitli z-bufer aniqligi ~1/near ga proporsional, 10 da
  // esa kromkaning 0.4 mm surilishi sig'dirish masofasida atigi 2.3 birlik
  // bo'lib, uzoqlashtirilganda qizil chiziq panel ichiga kirib "titrardi".
  // 40 mm dan yaqinga hech narsa tushmaydi: `minDistance` (0.12 × eng katta
  // o'lcham) 460 fayldagi eng kichik mahsulotda ham 52.8 mm.
  const camera = new PerspectiveCamera(45, 1, 40, 200_000)
  const controls = new OrbitControls(camera, canvas)
  controls.enableDamping = true
  controls.dampingFactor = 0.12
  controls.rotateSpeed = 0.85
  // SURISH O'CHIQ: mahsulot doim markazda turadi. Yoqilganda ikki barmoq
  // tasodifan uni ekran chetiga surib yuborardi va "tiklash"dan boshqa yo'l
  // qolmasdi. Aylantirish esa CHEKLANMAGAN — tagini ham ko'rish mumkin,
  // yig'uvchiga taglik qanday biriktirilgani kerak bo'ladi.
  controls.enablePan = false
  // Yaqinlashtirish BARMOQ (kursor) tomonga: ilgari u doim mahsulot markaziga
  // borardi va usta chetdagi shkafning ichiga yaqinlasha olmasdi — faqat
  // o'rtadagisiga. Uzoqlashganda nishon o'zi markazga qaytadi (`tick`), ya'ni
  // butun mahsulot ko'rinayotganda u baribir markazda.
  controls.zoomToCursor = true

  // Muhit yoritgichi: plita yuzasi yumshoq aks etadi, panellar "qog'oz"
  // bo'lib qolmaydi. Bir marta yasaladi va sahna bo'ylab ishlatiladi.
  const pmrem = new PMREMGenerator(renderer)
  const muhit = pmrem.fromScene(new RoomEnvironment(), 0.04)
  scene.environment = muhit.texture
  // `RoomEnvironment` — yorug' oq studiya. To'liq kuchida plita rangi yuvilib
  // ketadi va yog'och ham, oq ham bir xil krem bo'lib qoladi.
  //
  // 0.42 dan 0.22 ga TUSHIRILDI. Muhit xaritasi DUNYOGA qotirilgan: shiftga
  // qaragan yuza yorug', polga qaragani deyarli qorong'u. U yoritishning
  // asosiy qismini bergani uchun mahsulotni pastdan aylantirganda ko'rinadigan
  // yuzalar almashib, RANG O'ZGARGANDEK tuyulardi — kulrang eshik joyida
  // qolib, yonidagi yog'och qorayardi va kulrang "oqarib" ketardi.
  // O'lchandi (02 tumba, 3/4 burchakdan 18 qadam pastga): yog'och 157 -> 131,
  // kulrang 155 -> 155, ya'ni ikkisining farqi -2 dan +24 ga sakrardi.
  // Yoritish KAMERAGA ko'chirilgach (pastdagi asosiy + to'ldiruvchi) bu farq
  // +7 ga tushdi, umumiy yorqinlik esa `toneMappingExposure` bilan saqlandi.
  scene.environmentIntensity = 0.22

  // Asosiy yorug'lik KAMERAGA biriktirilgan: qaragan tomon doim yoritilgan
  // bo'ladi. Qo'zg'almas "quyosh"da mahsulotni aylantirib orqa tomonga
  // o'tilganda butun model kulrangga aylanib qolardi — yig'uvchi aynan
  // orqasini ko'rmoqchi bo'ladi.
  const quyosh = new DirectionalLight(0xffffff, 1.6)
  // Yuqoridan va yonboshdan — o'qdan 27°. To'g'ridan yoritilsa suratdagi
  // "chaqnoq" kabi yassi chiqadi va panel qirralarining hajmi yo'qoladi.
  //
  // NISHON ham kameraga biriktirilishi SHART. Busiz u dunyo markazida
  // qolardi, yo'nalish esa `yorug'lik - nishon` dan olinadi: sahna
  // MILLIMETRDA, ya'ni surilish kameradan atigi 1.3 mm narida edi, kamera
  // esa mahsulotdan 2.8-17 METR uzoqda. Natijada surilish yo'qolib, sof
  // "chaqnoq" yoritgich qolardi — modelning yassi ko'rinishi shundan edi.
  // Nishon kamerada bo'lsa burchak zoomdan MUSTAQIL (ilgari 8°dan 53°gacha
  // suzardi). Z ni 2.0 qilish shart: 0.3 da burchak 77° bo'lib, fasadga
  // to'g'ridan yorug'lik umuman tushmasdi (N·L = 0.00 o'lchandi).
  quyosh.position.set(0.5, 0.9, 2.0)
  camera.add(quyosh)
  camera.add(quyosh.target)
  // TO'LDIRUVCHI — qarama-qarshi tomondan va pastdan, kuchi asosiyning 44% i.
  // Vazifasi: qaralayotgan tomon HECH QACHON qop-qora bo'lmasin. Busiz
  // mahsulotni pastdan aylantirganda tag panellar qorayib, yonidagi kulrang
  // eshik oqarib ketgandek ko'rinardi.
  const toldiruvchi = new DirectionalLight(0xffffff, 0.7)
  toldiruvchi.position.set(-0.6, -0.4, 1.2)
  camera.add(toldiruvchi)
  camera.add(toldiruvchi.target)
  scene.add(camera)

  const group = new Group()
  scene.add(group)

  const soyaTex = shadowTexture()
  const soya = new Mesh(
    new PlaneGeometry(1, 1),
    new MeshBasicMaterial({
      map: soyaTex,
      transparent: true,
      depthWrite: false,
    }),
  )
  soya.rotation.x = -Math.PI / 2
  soya.renderOrder = -1
  soya.visible = false
  scene.add(soya)

  const materiallar = new Map<string, MeshStandardMaterial>()
  /** Material indeksi -> nomi. Ko'rinish NOMDAN chiqariladi (`model.ts`),
   * indeksdan emas: bir xil material har mahsulotda bir xil ko'rinishi kerak. */
  let matNomlari: string[] = []
  const materialFor = (mat: number, holat: Holat) => {
    const key = `${mat}:${holat}`
    let m = materiallar.get(key)
    if (!m) {
      const nom = matNomlari[mat] ?? ""
      const yuza = holat === "oddiy" ? maxsusYuza(nom) : undefined
      const oyna = yuza === "shisha"
      const xira = holat === "xira"
      const kontur = holat === "kontur"
      const qoshni = holat === "qoshni"
      m = new MeshStandardMaterial({
        color:
          holat === "tanlangan"
            ? RANG.tanlangan
            : holat === "topilgan"
              ? RANG.topilgan
              : materialColor(nom),
        roughness: materialRoughness(nom),
        // Ko'zgu muhitni aks ettiradi; furnitura metali (nikel, xrom) yarim
        metalness: yuza === "kozgu" ? 0.9 : isMetal(nom) ? 0.6 : 0,
        transparent: xira || kontur || qoshni || oyna,
        // Xira: kontekst yo'qolmasin, lekin tanlangani ajralib tursin.
        // Kontur: fasad qayerda turgani bilinsin (qirrasi), ichini to'smasin.
        // Qo'shni: tanlangan detal ORTIDA qolsa ham uni to'smasin.
        opacity: xira ? 0.16 : kontur ? 0.05 : qoshni ? 0.42 : oyna ? 0.34 : 1,
        depthWrite: !xira && !kontur && !qoshni && !oyna,
        side: DoubleSide,
        // `zamena` qatlami Bazisdagidek ko'rinmaydi — ostidagi fasad ko'rinadi.
        // Qidiruvda topilsa yoki tanlansa esa o'z rangida: joyi bilinsin.
        visible: !(
          (holat === "oddiy" || xira || kontur || qoshni) &&
          maxsusYuza(nom) === "zamena"
        ),
      })
      materiallar.set(key, m)
    }
    return m
  }

  /** Tekstura rasmlari — mahsulotlar orasida UMUMIY (bir xil `dub vatan`
   * boshqa mahsulotda qayta yuklanmaydi). Burilgan nusxa `clone()` — rasm
   * manbasi bitta, GPU ga bir marta yuklanadi. */
  const teksturalar = new Map<string, Texture>()
  const yuklangan = new Set<string>()
  const yuklovchi = new TextureLoader()
  const anizotropiya = Math.min(8, renderer.capabilities.getMaxAnisotropy())

  /** Rasmni materialga qo'yadi — FAQAT yuklangandan keyin. Undan oldin yuza
   * rasmning o'rtacha rangida turadi (`MAT_RANG` aynan shu o'rtacha), ya'ni
   * almashuv ko'zga tashlanmaydi; bo'sh tekstura esa yuzani qora qilardi. */
  const teksturaQoy = (m: MeshStandardMaterial) => {
    const t = m.userData.tex as Tekstura
    const burilgan = m.userData.burilgan as boolean
    const key = `${t.url}:${burilgan ? "b" : "t"}`
    let tex = teksturalar.get(key)
    if (!tex) {
      tex = (teksturalar.get(t.url) as Texture).clone()
      // Kontur mm da: bitta rasm — bitta `eni x boyi` tayl (katalogdagi,
      // 240 yozuvdan 215 tasida 1000 mm). Tola `TexDir` bo'yicha kontur X yoki
      // Y bo'ylab (`r`); rasmdagi tola odatda bo'yi bo'ylab, stoleshnitsa
      // fotosida eni bo'ylab (`tolaU`) — ikkisi farq qilsa 90°.
      tex.repeat.set(1 / t.eni, 1 / t.boyi)
      tex.rotation = (burilgan ? Math.PI / 2 : 0) + (t.burchak * Math.PI) / 180
      teksturalar.set(key, tex)
    }
    m.map = tex
    m.color.set("#ffffff")
    m.needsUpdate = true
  }

  /** Panel materiali. Naqshli materialda (yog'och, marmar) YUZALARIGA rasm,
   * yon devorlariga tekis rang: kromka chizilmaydi, `ExtrudeGeometry` ning
   * 1-guruhi (yon devorlar) tekis qoladi. Tanlov/qidiruv holatida — tekis. */
  const panelMaterial = (i: number, holat: Holat): Material | Material[] => {
    const panel = panels[i]
    const tekis = materialFor(panel.m, holat)
    const t =
      holat === "oddiy" &&
      ekstruziya[i] &&
      materialTexture(matNomlari[panel.m] ?? "")
    if (!t) return tekis
    const burilgan = Boolean(panel.r) !== t.tolaU
    const key = `${panel.m}:tex:${burilgan ? "b" : "t"}`
    let yuza = materiallar.get(key)
    if (!yuza) {
      yuza = tekis.clone()
      yuza.userData = { tex: t, burilgan }
      materiallar.set(key, yuza)
      if (yuklangan.has(t.url)) teksturaQoy(yuza)
      else if (!teksturalar.has(t.url)) {
        const asos = yuklovchi.load(t.url, () => {
          yuklangan.add(t.url)
          for (const m of materiallar.values())
            if (m.userData.tex?.url === t.url) teksturaQoy(m)
          belgila()
        })
        asos.colorSpace = SRGBColorSpace
        // Oddiy foto (chetlari tutashmaydi) takrorlansa tayl chegarasida qattiq
        // chiziq qolardi (`110026` bo'yiga). Ko'zgu ulanishda chet o'zi bilan
        // tutashadi: tola uzilmaydi, faqat naqsh aks etadi.
        asos.wrapS = t.aksU ? MirroredRepeatWrapping : RepeatWrapping
        asos.wrapT = t.aksV ? MirroredRepeatWrapping : RepeatWrapping
        asos.anisotropy = anizotropiya
        teksturalar.set(t.url, asos)
      }
    }
    return [yuza, tekis]
  }

  const qirraMat = new LineBasicMaterial({
    color: RANG.qirra,
    transparent: true,
    opacity: 0.3,
  })
  /** QUYUQ dekor uchun och qirra. Quyuq ko'k chiziq venge (#6d5647) ustida
   * kontrasti 1.05, qora (#2a2a2c) ustida 1.20 — ya'ni ko'rinmaydi, holbuki
   * chiziq aynan "bir xil rangdagi qo'shni panellar bitta blokka aylanib
   * qolmasin" uchun bor. Quyuq dekorlar ishlatilishning 17.5% i. */
  const qirraOchMat = new LineBasicMaterial({
    color: "#c9d1dc",
    transparent: true,
    opacity: 0.35,
  })
  /** Fasad konturi — dekor rangidan qat'i nazar quyuq: yuzasi deyarli
   * shaffof, chiziq esa ichkaridagi detallar va och fon ustida ko'rinishi kerak */
  const konturMat = new LineBasicMaterial({
    color: RANG.qirra,
    transparent: true,
    opacity: 0.5,
    depthWrite: false,
  })
  /** Tanlov va qidiruvdagi FON qirrasi — juda xira: mahsulot tuzilishi
   * (qaysi shkaf, qaysi qavat) o'qilsin, lekin tanlangan detal ustida
   * "qafas" bo'lmasin. DetalQR barcha qirrani to'liq chizadi — 300 panelli
   * oshxonada u sim to'riga aylanadi. */
  const fonQirraMat = new LineBasicMaterial({
    color: RANG.qirra,
    transparent: true,
    opacity: 0.13,
    depthWrite: false,
  })
  /** Tanlangan detal konturi — boshqa panellar ORTIDAN ham ko'rinadi
   * (`depthTest` siz, eng oxirida chiziladi): yuzasi old paneldan xiralashsa
   * ham detalning shakli va joyi aniq qoladi */
  const tanlanganQirraMat = new LineBasicMaterial({
    color: RANG.tanlanganQirra,
    transparent: true,
    depthTest: false,
    depthWrite: false,
  })
  /** Rangning nisbiy yorqinligi (sRGB). 0.18 dan pasti — quyuq dekor. */
  const yorugmi = (hex: string): boolean => {
    const n = Number.parseInt(hex.slice(1), 16)
    const k = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => {
      const c = v / 255
      return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
    })
    return 0.2126 * k[0] + 0.7152 * k[1] + 0.0722 * k[2] > 0.18
  }

  /** Sahna obyektlari: AVVAL panellar (`Mesh`, indeksi `panels` bilan bir xil),
   * keyin furnitura (`Group` — har materialli qismi alohida `Mesh`). Harakat
   * massivlari (`asl`, `ilgaklar`, `birlik`, `ochiqlik`...) ikkalasini qamraydi —
   * eshikdagi tutqich eshik bilan birga ochiladi. Bosish, qidiruv va qirra
   * chizig'i esa faqat panellarda. */
  let meshes: Object3D[] = []
  /** Furnitura geometriyasi — nusxalar o'rtasida UMUMIY, bir marta dispose */
  let furnGeo: BufferGeometry[] = []
  /** Har panelning qirra chizig'i — tanlov/qidiruvda fondagisi juda xira (`fonQirraMat`, `applyStates`);
   *  xona yuzasi va yashirin `zamena` qatlamida chizilmaydi */
  let qirralar: LineSegments[] = []
  /** Panel konturdan cho'zilganmi (tekstura faqat shunda — `BoxGeometry` UV'si 0..1) */
  let ekstruziya: boolean[] = []
  let panels: BazisPanel[] = []
  let asl: Vector3[] = []
  let aslQuat: Quaternion[] = []
  /** Ochilgan holat — faqat harakatlanadigan panelda to'ladi */
  let ochiqPos: (Vector3 | null)[] = []
  let ochiqQuat: (Quaternion | null)[] = []
  /** Burilib ochiladigan panelning o'qi (`ilgak.ts`); tortmada va harakatsizda `null` */
  let ilgaklar: (Ilgak | null)[] = []
  let yonalish: Vector3[] = []
  /** Panel markazi — guruh koordinatalarida (fokus va ochish shundan) */
  let markazlar: Vector3[] = []
  /** Panel va furnitura qutisi — guruh fazosida, YOPIQ holatda (qo'shnilik) */
  let qutilar: Box3[] = []
  /** Tanlangan detalga (istalgan nusxasiga) tegib turganlar — `setSelected` */
  let qoshni = new Set<number>()
  const markaz = new Vector3()
  /** Kameraning nishoni va gabaritning yarmi — guruh siljitilgandan KEYINGI holat */
  const fokus = new Vector3()
  const yarimOlcham = new Vector3(500, 500, 500)
  let olcham = 1000
  let tanlangan = new Set<number>()
  let topilgan = new Set<number>()
  /** Xona yuzalari (devor, pol) — doim xira va bosilmaydi. Kafel (devor
   * qoplamasi) — oddiy panel, faqat gabaritga kirmaydi (`model.ts: mebelEmas`) */
  let xona = new Set<number>()
  /** `zamena` qatlamlari — ko'rinmaydi, bosilmaydi (qidiruvda topilmasa) */
  let shaffof = new Set<number>()
  /** «Ichki» da konturga aylanadiganlar — `meshes` indekslari (`fasadlar`) */
  let fasad = new Set<number>()
  /** Foydalanuvchi tanlovi (boshqaruvdagi segment) — model almashsa ham qoladi */
  let ichkiKorinish = false
  let explode = 0
  /** Har panelning harakat birligi; harakatsiz panelda `null` */
  let birlik: (number | null)[] = []
  /** Har panelning ochilganligi 0..1 — kaskadda birliklar har xil nuqtada */
  let ochiqlik = new Float32Array(0)
  /** Joriy harakat: panel `dan` dan `ga` ga, `boshi` vaqtidan (kechikish bilan) */
  let dan = new Float32Array(0)
  let ga = new Float32Array(0)
  let boshi = new Float64Array(0)
  const ajratish = { dan: 0, ga: 0, boshi: 0 }
  /** Harakat davomiyligi; `prefers-reduced-motion` da 0 — holat darhol almashadi */
  let davom = HARAKAT_MS
  let harakatFrame = 0
  /** `focusOn` dan OLDINGI masofa — kartochka yopilganda shunga qaytiladi */
  let fokusdanOldin = 0
  /** Butun mahsulot ekranga sig'adigan masofa (`resetView` hisoblaydi) */
  let sigdirMasofa = 1000

  /** Kamera tween'i. BITTA tutqich: yangi tween eskisini bekor qiladi —
   * ilgari `focusOn` o'z siklini saqlamasdi va ikkita sikl bir vaqtda
   * `camera.position` ga yozardi. */
  let tweenFrame = 0
  const tween = (ms: number, qadam: (k: number) => void) => {
    cancelAnimationFrame(tweenFrame)
    const t0 = performance.now()
    const yur = () => {
      const t = Math.min(1, (performance.now() - t0) / ms)
      // easeOutCubic: harakat oxirida sekinlashadi, ko'z kuzatib ulguradi
      qadam(1 - (1 - t) ** 3)
      controls.update()
      belgila()
      tweenHarakatda = t < 1
      if (t < 1) tweenFrame = requestAnimationFrame(yur)
    }
    yur()
  }

  /** Sahna o'zgardi — keyingi kadrda qayta chiziladi (pastdagi `tick`). */
  let kir = true
  const belgila = () => {
    kir = true
  }
  // ZOOM shu yerda tirilgan: `OrbitControls` g'ildirak va pinch'ni o'z ichida
  // qayta ishlab, `update()` ni O'ZI chaqiradi. Shundan keyin `tick` dagi
  // `update()` "o'zgarish yo'q" deb qaytaradi va kadr chizilmaydi — kamera
  // yaqinlashgan, ekran esa eski holatda qolardi (brauzerda o'lchandi:
  // 20 ta g'ildirak tiqillashidan keyin 0 ta draw call, keyin bitta piksel
  // aylantirilganda ko'rinish birdan sakrab o'zgarardi).
  controls.addEventListener("change", belgila)

  const holatFor = (i: number): Holat => {
    // Xona yuzasi hech qachon to'liq ko'rinmaydi: 100 mm qalin devor va pol
    // mahsulotni berk qutiga solib qo'yardi (460 modelning 23% ida bor).
    // Butunlay o'chirilmaydi — mahsulot qayerga qo'yilishi bilinib tursin.
    if (xona.has(i)) return "xira"
    // Tanlov qidiruvdan USTUN: ilgari qolgan topilganlar to'q ko'k va shaffof
    // emas bo'lib qolardi va tanlangan detalni yopib qo'yardi (`03_0` dan
    // `03_001` tanlanganda yon devor qo'shni `03_*` panellar ortida qoldi).
    // Tanlovda uch qavat: detalning o'zi, unga TEGIB turgan panellar (nimaga
    // ulanadi — ustaning asosiy savoli) va xira fon. Unga o'rnatilgan
    // furnitura (ilgak, tutqich) — o'z rangida.
    const holat: Holat = tanlangan.size
      ? tanlangan.has(i)
        ? "tanlangan"
        : qoshni.has(i)
          ? i < panels.length
            ? "qoshni"
            : "oddiy"
          : "xira"
      : topilgan.size
        ? topilgan.has(i)
          ? "topilgan"
          : "xira"
        : "oddiy"
    // «Ichki»: fasad tanlov va qidiruvda ham kontur — xira (0.16) fasad
    // ichkaridagi tanlangan detalni baribir pardalab turardi. Fasadning
    // O'ZI topilsa yoki tanlansa — o'z rangida.
    return ichkiKorinish &&
      fasad.has(i) &&
      (holat === "oddiy" || holat === "xira" || holat === "qoshni")
      ? "kontur"
      : holat
  }

  const applyStates = () => {
    meshes.forEach((obj, i) => {
      const holat = holatFor(i)
      if (i < panels.length) {
        ;(obj as Mesh).material = panelMaterial(i, holat)
        // Qirra: tanlovda fonniki juda xira (to'liq kuchda u tanlangan detal
        // ustida "qafas" bo'lardi), tanlanganniki — boshqa panellar ortidan
        // ham ko'rinadigan kontur. Xona yuzasi va `zamena` qatlamida yo'q.
        const qirra = qirralar[i]
        const fon =
          (tanlangan.size > 0 || topilgan.size > 0) &&
          (holat === "xira" || holat === "kontur")
        qirra.visible =
          !xona.has(i) &&
          !(shaffof.has(i) && holat !== "tanlangan" && holat !== "topilgan")
        qirra.material =
          holat === "tanlangan"
            ? tanlanganQirraMat
            : fon
              ? fonQirraMat
              : holat === "kontur"
                ? konturMat
                : (qirra.userData.asl as Material)
        qirra.renderOrder = holat === "tanlangan" ? 10 : 0
        return
      }
      // Fasad furniturasi «Ichki» da butunlay yashirin: qirra chizig'i yo'q,
      // 5% dagi qora tutqich va ilgak esa kulrang dog' bo'lib qolardi
      obj.visible = holat !== "kontur"
      for (const qism of obj.children)
        (qism as Mesh).material = materialFor(qism.userData.m as number, holat)
    })
    belgila()
  }

  const clear = () => {
    gabaritQuti.makeEmpty()
    gabaritQirra = [[], [], []]
    gabaritTomon.set(1, 1, 1)
    bazisOlcham = []
    olchamNusxa = -1
    for (const obj of meshes) {
      if (!(obj instanceof Mesh)) continue
      obj.geometry.dispose()
      for (const child of obj.children) {
        if (child instanceof LineSegments) child.geometry.dispose()
      }
    }
    for (const g of furnGeo) g.dispose()
    furnGeo = []
    group.clear()
    // Materiallar model bo'yicha (oyna indekslari almashadi) — eskilarini
    // tashlab ketsak GPU xotirasi mahsulot almashtirgan sayin o'sardi.
    for (const m of materiallar.values()) m.dispose()
    materiallar.clear()
    meshes = []
    qirralar = []
    ekstruziya = []
    panels = []
    asl = []
    aslQuat = []
    ochiqPos = []
    ochiqQuat = []
    ilgaklar = []
    yonalish = []
    markazlar = []
    qutilar = []
    qoshni = new Set()
    tanlangan = new Set()
    // Holat ham tiklanadi: busiz yangi mahsulot eski modelning ochilganligini
    // va qidiruv natijasini meros qilib olardi.
    topilgan = new Set()
    xona = new Set()
    shaffof = new Set()
    fasad = new Set()
    cancelAnimationFrame(harakatFrame)
    birlik = []
    ochiqlik = new Float32Array(0)
    dan = new Float32Array(0)
    ga = new Float32Array(0)
    boshi = new Float64Array(0)
    Object.assign(ajratish, { dan: 0, ga: 0, boshi: 0 })
    explode = 0
    fokusdanOldin = 0
    soya.visible = false
  }

  const load = (model: BazisModel) => {
    clear()
    panels = model.panels
    matNomlari = model.mats
    model.panels.forEach((p, i) => {
      if (XONA_YUZASI.test(model.mats[p.m] ?? "")) xona.add(i)
      if (maxsusYuza(model.mats[p.m] ?? "") === "zamena") shaffof.add(i)
    })
    fasad = fasadlar(model)
    const quti = new Box3()
    for (const [i, panel] of model.panels.entries()) {
      const shape = shapeFor(panel)
      ekstruziya.push(Boolean(shape))
      const geo = shape
        ? new ExtrudeGeometry(shape, {
            depth: Math.max(panel.t, 1),
            bevelEnabled: false,
          })
        : new BoxGeometry(
            panel.s[0] || 1,
            panel.s[1] || 1,
            Math.max(panel.t, 1),
          )
      if (shape && panel.cp) kes(geo, panel.cp)
      const tex = shape && materialTexture(model.mats[panel.m] ?? "")
      if (tex) naqshSiljit(geo, tex, Boolean(panel.r) !== tex.tolaU, i)
      const mesh = new Mesh(geo, materialFor(panel.m, "oddiy"))
      mesh.position.fromArray(panel.p)
      mesh.quaternion.fromArray(panel.q)
      mesh.updateMatrix()
      // Qirra chizig'i mebelni "o'qishli" qiladi: busiz bir xil rangdagi
      // qo'shni panellar bitta yaxlit blokka aylanib ko'rinadi.
      const qirra = new LineSegments(
        new EdgesGeometry(geo, 30),
        yorugmi(materialColor(model.mats[panel.m] ?? ""))
          ? qirraMat
          : qirraOchMat,
      )
      qirra.userData.asl = qirra.material
      mesh.add(qirra)
      qirralar.push(qirra)
      group.add(mesh)
      meshes.push(mesh)
      // Gabarit GURUH koordinatalarida hisoblanadi: dunyo matritsasi guruh
      // siljitilgandan keyin o'zgaradi va ikki o'lchov bir-biriga mos kelmasdi.
      geo.computeBoundingBox()
      const b = (geo.boundingBox as Box3).clone().applyMatrix4(mesh.matrix)
      // Xona gabaritga KIRMAYDI: 4.2 m li devor bilan hisoblanganda kamera
      // oshxonani emas, xonani sig'dirardi va soya dog'i ham shuncha kengayardi.
      if (!xona.has(i)) quti.union(b)
      if (!mebelEmas(model.mats[panel.m] ?? "")) gabaritQuti.union(b)
      markazlar.push(b.getCenter(new Vector3()))
      qutilar.push(b)
    }
    // Furnitura: geometriya har mesh uchun BIR MARTA, nusxalar uni bo'lishadi
    // (bitta oshxonada bir xil ilgak 59 marta).
    const geolar = (model.meshes ?? []).map((qismlar) =>
      qismlar.map(([m, uchlar, normallar, indekslar]) => {
        const g = new BufferGeometry()
        g.setAttribute("position", new Float32BufferAttribute(uchlar, 3))
        g.setAttribute("normal", new Float32BufferAttribute(normallar, 3))
        g.setIndex(indekslar)
        g.computeBoundingBox()
        furnGeo.push(g)
        return { g, m }
      }),
    )
    for (const f of model.furn ?? []) {
      const obj = new Group()
      const b = new Box3()
      obj.position.fromArray(f.p)
      obj.quaternion.fromArray(f.q)
      obj.updateMatrix()
      for (const { g, m } of geolar[f.k] ?? []) {
        const qism = new Mesh(g, materialFor(m, "oddiy"))
        qism.userData.m = m
        obj.add(qism)
        b.union((g.boundingBox as Box3).clone().applyMatrix4(obj.matrix))
      }
      group.add(obj)
      meshes.push(obj)
      quti.union(b)
      markazlar.push(b.getCenter(new Vector3()))
      qutilar.push(b)
    }
    quti.getCenter(markaz)
    quti
      .getSize(yarimOlcham)
      .multiplyScalar(0.5)
      .max(new Vector3(1, 1, 1))
    olcham = Math.max(yarimOlcham.x, yarimOlcham.y, yarimOlcham.z) * 2
    // Mahsulot polda turgandek: markazi o'qlarda, tagi nolda.
    group.position.set(-markaz.x, -quti.min.y, -markaz.z)
    fokus.set(0, yarimOlcham.y, 0)
    // Soya mahsulot tagida, izidan bir yarim barobar keng — chetga qarab
    // yo'qolgani uchun o'lchamni katta olish kerak.
    soya.scale.set(yarimOlcham.x * 3.4, yarimOlcham.z * 3.4, 1)
    soya.position.set(0, 0.5, 0)
    soya.visible = true
    asl = meshes.map((m) => m.position.clone())
    aslQuat = meshes.map((m) => m.quaternion.clone())
    gabaritQiymat = gabarit(model)
    gabaritQirra = gabaritQirralari(model)
    bazisOlcham = (model.d ?? []).map((d) => ({
      v: d.v,
      a: new Vector3().fromArray(d.a),
      b: new Vector3().fromArray(d.b),
      o: new Vector3().fromArray(d.o),
      g: d.g,
    }))
    // Panellar va furnitura BIR ro'yxatda — `meshes` bilan bir xil tartibda
    const elementlar = harakatElementlari(model)
    ochiqPos = elementlar.map((p) =>
      p.po ? new Vector3().fromArray(p.po) : null,
    )
    ochiqQuat = elementlar.map((p) =>
      p.qo ? new Quaternion().fromArray(p.qo) : null,
    )
    ilgaklar = meshes.map((_, i) => {
      const po = ochiqPos[i]
      const qo = ochiqQuat[i]
      return po && qo ? ilgakOqi(asl[i], aslQuat[i], po, qo) : null
    })
    birlik = elementlar.map(harakatBirligi)
    ochiqlik = new Float32Array(meshes.length)
    dan = new Float32Array(meshes.length)
    ga = new Float32Array(meshes.length)
    boshi = new Float64Array(meshes.length)
    yonalish = markazlar.map((c) => {
      const v = c.clone().sub(markaz)
      // Markazda turgan panel uchun yo'nalish yo'q — joyida qolsin
      return v.lengthSq() < 1 ? v.set(0, 0, 0) : v.normalize()
    })
    applyStates()
    joylash()
    resetView()
  }

  /** Berilgan yo'nalishdan qaraganda butun mahsulot sig'adigan masofa.
   *
   * Gabarit KAMERA ramkasiga proyeksiyalanadi. Sig'dirish sharidan
   * foydalansak yassi mahsulot (3.2 x 2.3 x 0.45 m) ekranning yarmini bo'sh
   * qoldirardi. Telefonda (bo'yi enidan katta) chegaralovchi burchak
   * GORIZONTAL, shuning uchun ikkalasining KICHIGI olinadi — aks holda keng
   * oshxona chap va o'ngdan kesilib qolardi. */
  const kerakliMasofa = (burchak: Vector3) => {
    const vertikal = (camera.fov * Math.PI) / 360
    const gorizontal = Math.atan(Math.tan(vertikal) * camera.aspect)
    const eksX = new Vector3().crossVectors(camera.up, burchak).normalize()
    const eksY = new Vector3().crossVectors(burchak, eksX).normalize()
    const proyeksiya = (e: Vector3) =>
      Math.abs(e.x) * yarimOlcham.x +
      Math.abs(e.y) * yarimOlcham.y +
      Math.abs(e.z) * yarimOlcham.z
    return (
      Math.max(
        proyeksiya(eksX) / Math.tan(gorizontal),
        proyeksiya(eksY) / Math.tan(vertikal),
      ) *
        1.06 +
      proyeksiya(burchak)
    )
  }

  /** Bazis eskizidagi kabi uch choraklik ko'rinish — mahsulot bir qarashda
   * tanaladi. */
  const sigdir = () => {
    const burchak = new Vector3(0.62, 0.42, 0.66).normalize()
    const d = kerakliMasofa(burchak)
    // Zoom chegaralari: ichiga tushib ketib yo'nalishni yo'qotib bo'lmaydi va
    // cheksiz uzoqlashib mahsulotni nuqtaga aylantirib ham bo'lmaydi.
    controls.minDistance = olcham * 0.12
    controls.maxDistance = d * 3
    sigdirMasofa = d
    controls.target.copy(fokus)
    camera.position.copy(fokus).addScaledVector(burchak, d)
    controls.update()
    belgila()
  }

  const resetView = () => {
    resize()
    sigdir()
  }

  /** Qidiruvdan tanlangan detalga kamerani olib borish.
   *
   * Faqat RO'YXATDAN tanlanganda ishlaydi, 3D da bosilganda emas: foydalanuvchi
   * kodni qidirganda detal ichkarida, boshqa panellar ortida bo'lishi mumkin va
   * "qayerda?" degan savol javobsiz qolardi. Butun mahsulot ko'rinib turishi
   * uchun masofa keskin qisqartirilmaydi.
   *
   * Nishon — BARCHA nusxalarning umumiy markazi: ilgari birinchisiga borilardi
   * va telefonda 5 ta javonning pastkisi kartochka ostida qolardi. */
  const focusOn = (indexes: number[]) => {
    const quti = new Box3()
    // Markaz JORIY pozadan olinadi, `load` dagi yopiq holatdan emas: eshiklar
    // ochiq yoki panellar ajratilgan bo'lsa detal yarim metrgacha siljigan
    // bo'ladi va kamera bo'sh joyga uchib borardi.
    for (const i of indexes) if (meshes[i]) quti.expandByObject(meshes[i])
    if (quti.isEmpty()) return
    const qayerda = quti.getCenter(new Vector3())
    const yonalish = camera.position.clone().sub(controls.target).normalize()
    // Sig'dirish masofasining uchdan ikkisi: detal yaqinlashadi, lekin
    // mahsulotning qolgani ham ko'rinib turadi — "qayerda" degan savolga
    // javob aynan ATROFI bilan tushunarli bo'ladi.
    const d = Math.min(
      Math.max(sigdirMasofa * 0.62, controls.minDistance * 2),
      controls.maxDistance,
    )
    // Fokus — VAQTINCHALIK chekinish: kartochka yopilganda kamera qayerdan
    // kelgan bo'lsa o'sha masofaga qaytadi. Busiz foydalanuvchi detalning
    // burniga tiralgan holda qolib ketardi.
    if (fokusdanOldin === 0)
      fokusdanOldin = camera.position.distanceTo(controls.target)
    const bosh = controls.target.clone()
    const d0 = camera.position.distanceTo(controls.target)
    tween(420, (k) => {
      controls.target.lerpVectors(bosh, qayerda, k)
      camera.position
        .copy(controls.target)
        .addScaledVector(yonalish, d0 + (d - d0) * k)
    })
  }

  /** Nishonni mahsulot markaziga qaytaradi — detal tanlovi yopilganda.
   * Busiz orbit markazi o'sha detalda qolib, aylantirish g'alati tuyulardi. */
  const nishonniQaytar = () => {
    // Faqat qidiruvdagi `focusOn` qaytariladi: barmoq tomon yaqinlashtirilgan
    // nishon (`zoomToCursor`) — foydalanuvchining o'zi tanlagani, kartochka
    // yopilganda kamera undan sakrab ketmasin
    if (!fokusdanOldin) return
    const bosh = controls.target.clone()
    const yonalish = camera.position.clone().sub(controls.target).normalize()
    const d0 = camera.position.distanceTo(controls.target)
    const d1 = fokusdanOldin
    fokusdanOldin = 0
    tween(360, (k) => {
      controls.target.lerpVectors(bosh, fokus, k)
      camera.position
        .copy(controls.target)
        .addScaledVector(yonalish, d0 + (d1 - d0) * k)
    })
  }

  /** Ochilish va ajratishning kamera masofasiga ta'siri. */
  const kengayish = (o: number, e: number) => 1 + e * 0.5 + o * 0.18

  /** Panellarni JORIY holatga qo'yadi: ochilish va ajratish birga hisoblanadi.
   *
   * Ochilish — fayldagi HAQIQIY harakat (eshik ilgagi, tortma surmasi), ya'ni
   * yopiq va ochiq holat orasida: eshik o'z o'qi atrofida buriladi (`ilgak.ts`),
   * tortma to'g'ri chiziq bo'ylab suriladi. Ajratish — sun'iy: panel mahsulot
   * markazidan tashqariga suriladi. */
  const joylash = () => {
    meshes.forEach((mesh, i) => {
      const po = ochiqPos[i]
      const qo = ochiqQuat[i]
      const il = ilgaklar[i]
      const k = ochiqlik[i]
      if (k > 0 && il) {
        ilgakHolati(il, asl[i], aslQuat[i], k, mesh.position, mesh.quaternion)
      } else if (k > 0 && po && qo) {
        mesh.position.lerpVectors(asl[i], po, k)
        mesh.quaternion.slerpQuaternions(aslQuat[i], qo, k)
      } else {
        mesh.position.copy(asl[i])
        mesh.quaternion.copy(aslQuat[i])
      }
      if (explode > 0) {
        mesh.position.addScaledVector(yonalish[i], explode * olcham * 0.22)
      }
    })
    // Ajratilganda pastki detallar "pol" ostiga tushadi va shaffof soya diski
    // ularning ustiga tushib bo'yab qo'yardi.
    soya.visible = meshes.length > 0 && explode < 0.02
    belgila()
  }

  /** Harakatlanadigan panellarning o'rtacha ochilganligi — kamera masofasi uchun */
  const ortachaOchiqlik = () => {
    let s = 0
    let n = 0
    birlik.forEach((b, i) => {
      if (b === null) return
      s += ochiqlik[i]
      n++
    })
    return n ? s / n : 0
  }

  /** `boshi` dan boshlangan harakatning `hozir` dagi qiymati (easeOutCubic:
   * oxirida sekinlashadi, ko'z kuzatib ulguradi). Tugagach AYNAN `oxiri`. */
  const qiymat = (
    bosh: number,
    boshi: number,
    oxiri: number,
    hozir: number,
  ) => {
    const t = davom ? Math.max(0, (hozir - boshi) / davom) : 1
    return t >= 1 ? oxiri : bosh + (oxiri - bosh) * (1 - (1 - t) ** 3)
  }

  /** Bir kadr: har panel o'z vaqtida, ajratish esa hammasi birga. Kamera
   * masofasi eslab qolinmaydi — JORIY masofa nisbat bilan kengaytiriladi,
   * shuning uchun foydalanuvchining zoom'i saqlanadi. */
  const harakat = () => {
    const hozir = performance.now()
    const eski = kengayish(ortachaOchiqlik(), explode)
    let davomEtadi = false
    for (let i = 0; i < ochiqlik.length; i++) {
      if (ochiqlik[i] === ga[i]) continue
      ochiqlik[i] = qiymat(dan[i], boshi[i], ga[i], hozir)
      davomEtadi ||= ochiqlik[i] !== ga[i]
    }
    explode = qiymat(ajratish.dan, ajratish.boshi, ajratish.ga, hozir)
    davomEtadi ||= explode !== ajratish.ga
    joylash()
    const yangi = kengayish(ortachaOchiqlik(), explode)
    if (yangi !== eski) {
      const v = camera.position.clone().sub(controls.target)
      const d = Math.min(
        Math.max((v.length() * yangi) / eski, controls.minDistance),
        controls.maxDistance,
      )
      camera.position.copy(controls.target).addScaledVector(v.normalize(), d)
    }
    pozaHarakatda = davomEtadi
    if (davomEtadi) harakatFrame = requestAnimationFrame(harakat)
  }

  /** Ko'rinish holati: qaysi birliklar ochiq va ajratilganlik — BIRGA.
   *
   * Harakat sahnaning o'zida: Reactda har kadr holat yangilash telefonda kadr
   * tezligini yeydi. Holati o'zgargan birliklar KASKAD bo'lib boshlanadi —
   * ekrandagi joyiga qarab chapdan o'ngga, tepadan pastga to'lqin (yopilishda
   * teskari). Hammasi bir vaqtda qimirlasa ko'z qaysi eshik qayoqqa
   * ochilganini ilg'amasdi. Bitta birlik (kartochkadan) — kechikishsiz.
   * `prefers-reduced-motion` da harakat yo'q, holat darhol almashadi. */
  const setPose = (
    ochiqBirliklar: ReadonlySet<number>,
    yangiExplode: number,
  ) => {
    const hozir = performance.now()
    davom = window.matchMedia("(prefers-reduced-motion: reduce)").matches
      ? 0
      : HARAKAT_MS
    // O'zgaradigan birliklarning ekrandagi markazi (NDC: x o'ngga, y tepaga)
    const joy = new Map<number, { x: number; y: number; n: number }>()
    const v = new Vector3()
    // Matritsalar render paytida yangilanadi — undan oldin chaqirilsa eskisi qolardi
    group.updateMatrixWorld()
    camera.updateMatrixWorld()
    birlik.forEach((b, i) => {
      if (b === null || (ochiqBirliklar.has(b) ? 1 : 0) === ga[i]) return
      v.copy(markazlar[i]).applyMatrix4(group.matrixWorld).project(camera)
      const j = joy.get(b) ?? { x: 0, y: 0, n: 0 }
      j.x += v.x
      j.y += v.y
      j.n++
      joy.set(b, j)
    })
    const xs = [...joy.values()].map((j) => j.x / j.n)
    const ys = [...joy.values()].map((j) => j.y / j.n)
    const [x0, x1] = [Math.min(...xs), Math.max(...xs)]
    const [y0, y1] = [Math.min(...ys), Math.max(...ys)]
    // Ichki mexanizm — paneli yo'q birlik (pantograf, shim ilgichi, tortma
    // savat): eshik OCHILIB BO'LGACH chiqadi, yopilishda esa BIRINCHI qaytadi.
    // Bir vaqtda yursa u hali ochilayotgan shisha eshik ichidan o'tardi
    // (`3-Garderob`: ilgich va pantograf richagi eshik profilidan).
    const panelli = new Set(birlik.slice(0, panels.length))
    const ichki = (b: number) => !panelli.has(b)
    const ikkiBosqich =
      davom > 0 &&
      [...joy.keys()].some(ichki) &&
      [...joy.keys()].some((b) => !ichki(b))
    const kechikish = new Map<number, number>()
    for (const [b, j] of joy) {
      const ochilyapti = ochiqBirliklar.has(b)
      const keyin = ikkiBosqich && ichki(b) === ochilyapti
      const bosqich = keyin ? KASKAD_MS + davom : 0
      if (joy.size < 2 || !davom) {
        kechikish.set(b, bosqich)
        continue
      }
      const nx = x1 > x0 ? (j.x / j.n - x0) / (x1 - x0) : 0
      const ny = y1 > y0 ? (y1 - j.y / j.n) / (y1 - y0) : 0
      const t = 0.75 * nx + 0.25 * ny
      kechikish.set(b, bosqich + (ochilyapti ? t : 1 - t) * KASKAD_MS)
    }
    birlik.forEach((b, i) => {
      if (b === null || !kechikish.has(b)) return
      dan[i] = ochiqlik[i]
      ga[i] = ochiqBirliklar.has(b) ? 1 : 0
      boshi[i] = hozir + (kechikish.get(b) ?? 0)
    })
    if (yangiExplode !== ajratish.ga)
      Object.assign(ajratish, { dan: explode, ga: yangiExplode, boshi: hozir })
    cancelAnimationFrame(harakatFrame)
    harakat()
  }

  const setSelected = (indexes: number[]) => {
    tanlangan = new Set(indexes)
    // Tegish — yopiq holatdagi qutilar 2 mm ichida: eshik korpusga 1-2 mm
    // tirqish bilan turadi, javon yon devorga tiraladi. Qutilar o'qlarga
    // tekislangan, lekin mebel panellari ham deyarli hammasi shunday.
    qoshni = new Set()
    const tanlanganQuti = [...tanlangan]
      .map((i) => qutilar[i]?.clone().expandByScalar(2))
      .filter((b): b is Box3 => Boolean(b))
    if (tanlanganQuti.length)
      qutilar.forEach((b, i) => {
        if (tanlangan.has(i) || xona.has(i) || shaffof.has(i)) return
        if (tanlanganQuti.some((t) => t.intersectsBox(b))) qoshni.add(i)
      })
    applyStates()
  }

  const setFound = (indexes: Set<number>) => {
    topilgan = indexes
    applyStates()
  }

  // --- tanlash: surish bilan bosishni ajratamiz ---
  const ray = new Raycaster()
  const bosh = new Vector2()
  let bosildi = false
  /** Ekrandagi barmoqlar. IKKI barmoq — bu pinch, tanlash EMAS. Hisoblagich
   * emas, id to'plami: bekor qilingan barmoq (`pointercancel` — tizim imo-ishorasi,
   * qo'ng'iroq oynasi) `pointerup` bermaydi va hisoblagich 1 da qotib, keyingi
   * HAR bosish "ikkinchi barmoq" bo'lib, tanlash sahifa yangilanguncha o'lardi. */
  const barmoqlar = new Set<number>()

  const onDown = (e: PointerEvent) => {
    barmoqlar.add(e.pointerId)
    if (barmoqlar.size > 1) {
      // Ikkinchi barmoq tushdi: bu pinch. Busiz uning `pointerup` i o'z
      // tushgan nuqtasidan 8 px narida bo'lgani uchun "bosish" deb
      // hisoblanib, tanlangan detalni YO'QOTARDI (telefonda takrorlandi).
      bosildi = false
      return
    }
    bosh.set(e.clientX, e.clientY)
    bosildi = true
  }
  const onCancel = (e: PointerEvent) => {
    barmoqlar.delete(e.pointerId)
    bosildi = false
  }
  const onUp = (e: PointerEvent) => {
    barmoqlar.delete(e.pointerId)
    // 8 px dan ortiq surilgan bo'lsa — bu aylantirish edi, tanlash emas
    if (!bosildi || Math.hypot(e.clientX - bosh.x, e.clientY - bosh.y) > 8)
      return
    bosildi = false
    const r = canvas.getBoundingClientRect()
    ray.setFromCamera(
      new Vector2(
        ((e.clientX - r.left) / r.width) * 2 - 1,
        -((e.clientY - r.top) / r.height) * 2 + 1,
      ),
      camera,
    )
    // Qidiruv faol bo'lsa faqat TOPILGANLAR bosiladi: xira panel deyarli
    // ko'rinmaydi, lekin nur uchun to'siq bo'lib turardi va foydalanuvchi
    // ko'rmagan detalini tanlab olardi. Xona yuzasi esa hech qachon: nomi
    // qidiruvga mos kelsa ham u doim xira chiziladi.
    // Furnitura bosilmaydi: u detal emas, tutqich ustida bosilgan eshik tanlansin
    // «Ichki» dagi fasad konturi ham bosilmaydi: u ORTIDAGI detalni ko'rsatish
    // uchun kontur, bosish esa baribir fasadni tanlab qo'yardi.
    const nishon = meshes.filter(
      (_, i) =>
        i < panels.length &&
        !xona.has(i) &&
        holatFor(i) !== "kontur" &&
        // Ko'rinmas qatlam bosishni o'ziga olmasin — ostidagi fasad tanlansin
        (!shaffof.has(i) || topilgan.has(i)) &&
        (!topilgan.size || topilgan.has(i)),
    )
    const hit = ray.intersectObjects(nishon, false)[0]
    if (!hit) {
      onPick(null)
      return
    }
    const index = meshes.indexOf(hit.object as Mesh)
    onPick(index < 0 ? null : { panel: panels[index], index })
  }
  canvas.addEventListener("pointerdown", onDown)
  canvas.addEventListener("pointerup", onUp)
  canvas.addEventListener("pointercancel", onCancel)

  // --- o'lcham va kadr ---
  /** Pastki qatlam balandligi (px, tween bilan). Kadr uning yarmicha YUQORIGA
   * suriladi (`setViewOffset`), ya'ni markaz bo'sh joyning markaziga tushadi:
   * busiz fokuslangan detal va nusxalari kartochka ostida qolardi (08_008 ning
   * 5 nusxasidan 2 tasi). Orbit markazi joyida — faqat rasm suriladi, nur
   * ham shu proyeksiyadan otiladi. */
  let band = 0
  let bandFrame = 0
  const proyeksiya = () => {
    const { clientWidth: w, clientHeight: h } = canvas
    if (!w || !h) return
    camera.aspect = w / h
    if (band >= 1) camera.setViewOffset(w, h, 0, band / 2, w, h)
    else camera.clearViewOffset()
    camera.updateProjectionMatrix()
    belgila()
  }
  const setPastkiBand = (px: number) => {
    cancelAnimationFrame(bandFrame)
    const dan = band
    const t0 = performance.now()
    const qadam = () => {
      const t = Math.min(1, (performance.now() - t0) / 320)
      band = dan + (px - dan) * (1 - (1 - t) ** 3)
      proyeksiya()
      bandHarakatda = t < 1
      if (t < 1) bandFrame = requestAnimationFrame(qadam)
    }
    qadam()
  }

  // --- o'lchamlar ---
  /** Uch qavat (docs/13 §7):
   * * D1 — tanlangan detalning ENI va BO'YI o'z qirralarida, kameraga qaragan
   *   yuzada; tugmasiz, har kadrda. Kartochkadagi «716 × 400» qaysi tomonga
   *   tegishli ekanini ko'rsatadi;
   * * D1+ — bazischining shu detalga tegadigan o'lchamlari (javon balandligi
   *   bazischining o'z raqami bilan, taxmin emas);
   * * D2 — «O'lchamlar» tugmasi: gabarit va bazischining barcha o'lchamlari.
   * D1+ va D2 faqat kamera va harakat TO'XTAGANDA joylanadi (ortida panel bormi —
   * nur bilan), harakat paytida yashirin: har kadrda o'nlab nur telefonni yerdi.
   *
   * Chiziq — 3D (`LineSegments`), raqam — HTML yorliq: har burchakda tekis va bir
   * xil o'lchamda (DetalQR'dagi 3D matn burchak ostida o'qilmasdi). Yorliq bilan
   * chizig'i DOIM birga: chiziq juda qisqa bo'lsa, yorliqqa joy topilmasa
   * (tugmalar qatori, pastki panel, boshqa yorliq) yoki o'lcham panel ortida
   * qolsa — ikkalasi ham yashiriladi. */
  const olchamMat = new LineBasicMaterial({ color: "#284868" })
  const olchamChiziq = new LineSegments(new BufferGeometry(), olchamMat)
  olchamChiziq.frustumCulled = false
  olchamChiziq.visible = false
  scene.add(olchamChiziq)
  /** Yorliqlar hovuzi — kerak bo'lganicha o'sadi (bitta oshxonada 31 o'lcham) */
  const yorliqlar: HTMLSpanElement[] = []
  const yorliq = (k: number): HTMLSpanElement | undefined => {
    while (qatlam && yorliqlar.length <= k) {
      const s = document.createElement("span")
      s.className =
        "num pointer-events-none absolute top-0 left-0 whitespace-nowrap rounded-full border border-border bg-card/95 px-1.5 font-semibold text-[13px] text-foreground leading-5 shadow-sm"
      s.style.visibility = "hidden"
      qatlam.append(s)
      yorliqlar.push(s)
    }
    return yorliqlar[k]
  }
  /** D1 chizilgan nusxa — sakrab turmasligi uchun boshqa nusxa ekran markaziga
   * 20% dan ko'proq yaqin bo'lmaguncha almashmaydi */
  let olchamNusxa = -1
  /** `setYorliqZona` — `ModelViewer` ekrandagi haqiqiy o'lchamdan beradi */
  const yorliqZona = { ust: 72, past: 0 }
  /** «O'lchamlar» tugmasi (D2) */
  let olchamlarYoniq = false
  /** Gabarit — panellar qutisi GURUH fazosida (xona, `zamena` va furniturasiz),
   * qiymati sarlavhadagi bilan bir xil (`model.ts: gabarit`) */
  const gabaritQuti = new Box3()
  let gabaritQiymat: [number, number, number] = [0, 0, 0]
  /** Gabarit o'lchami chiziladigan haqiqiy qirralar — mahsulot fazosida */
  let gabaritQirra: GabaritQirrasi[][] = [[], [], []]
  /** Bazischining o'lchamlari (`d`) — guruh fazosida, yopiq holatda */
  let bazisOlcham: {
    v: number
    a: Vector3
    b: Vector3
    o: Vector3
    g?: number
  }[] = []
  /** Eshik harakati yoki kamera tween'i davom etmoqda — og'ir joylash kutadi */
  let pozaHarakatda = false
  let tweenHarakatda = false
  let bandHarakatda = false
  const nur = new Raycaster()
  const t2 = new Vector3()
  const ekranga = (v: Vector3) => {
    t2.copy(v).project(camera)
    return {
      x: ((t2.x + 1) / 2) * canvas.clientWidth,
      y: ((1 - t2.y) / 2) * canvas.clientHeight,
      oldinda: t2.z < 1,
    }
  }
  const yorliqOlchami = (s: HTMLSpanElement, matn: string) => {
    if (s.textContent !== matn) {
      s.textContent = matn
      s.dataset.eni = String(s.offsetWidth)
      s.dataset.boyi = String(s.offsetHeight)
    }
    return [Number(s.dataset.eni), Number(s.dataset.boyi)]
  }
  const matni = (v: number) => (Number.isInteger(v) ? String(v) : v.toFixed(1))

  /** Bitta o'lchamning bitta joylashuvi — dunyo fazosida */
  type Olcham = {
    qiymat: number
    /** O'lchangan ikki nuqta */
    a: Vector3
    b: Vector3
    /** Chiziq surilgan tomon — birlik vektor, `a-b` ga tik */
    n: Vector3
    /** Surilish, mm; `null` — ekranda `cheti` px (tik o'qning masshtabi) */
    surish: number | null
    cheti: number
    /** Ortida panel bormi — tekshirilsinmi (D1 da boshqa detallar xira) */
    tosiq: boolean
    /** Yorliq matni; yo'q bo'lsa — faqat qiymat */
    matn?: string
  }
  type Joy = { x: number; y: number; w: number; h: number }
  /** Chizilgan o'lcham chizig'i — ekranda */
  type Uch = {
    a: { x: number; y: number }
    b: { x: number; y: number }
    /** 3D yo'nalishi (birlik) — zanjirni ekrandagi tasodifiy bir chiziqdan ajratadi */
    yon: Vector3
  }

  /** Nuqta kameradan ko'rinmaydimi — oradagi panel, shisha yoki furnitura.
   * Xira (tanlovda), fasad konturi («Ichki»), `zamena` va xona yuzasi
   * to'smaydi: ular ko'rinmaydi yoki deyarli shaffof. Shisha to'sadi —
   * `depthWrite` siz u chiziqni to'smasdi, shkaf ichidagi o'lcham esa shisha
   * ortidan "suzib" ko'rinardi (DetalQR). */
  const tosuvchilar: Object3D[] = []
  const tosilgan = (p: Vector3) => {
    const yol = p.clone().sub(camera.position)
    const d = yol.length()
    nur.set(camera.position, yol.divideScalar(d))
    nur.far = d - 2
    return nur
      .intersectObjects(tosuvchilar, true)
      .some((h) => h.object instanceof Mesh && h.object.visible)
  }

  /** Nomzodlardan birinchi SIG'GANI chiziladi (qirra/tomon variantlari) */
  const chiz = (
    nomzodlar: Olcham[],
    k: number,
    bo: { x0: number; y0: number; x1: number; y1: number },
    qabul: Joy[],
    chiziqlar: number[],
    uchlar: Uch[],
  ): boolean => {
    const s = yorliq(k)
    if (!s) return false
    // Birlikli yorliq («600 mm», 62 px) sig'masa — o'sha joyda faqat raqam
    // («600», 38 px): telefonda qisqa chuqurlik chizig'iga birlik bilan
    // yorliq sig'masdi (sarlavhada «… × 600 mm» baribir yozilgan)
    const variantlar = nomzodlar.flatMap((o) =>
      o.matn ? [o, { ...o, matn: undefined }] : [o],
    )
    for (const o of variantlar) {
      const [lw, lh] = yorliqOlchami(s, o.matn ?? matni(o.qiymat))
      const a = ekranga(o.a)
      const b = ekranga(o.b)
      const piksel = Math.hypot(b.x - a.x, b.y - a.y)
      if (!a.oldinda || !b.oldinda || piksel < 1) continue
      const ab = o.b.clone().sub(o.a)
      const mmPx = ab.length() / piksel
      ab.normalize()
      const orta = o.a.clone().add(o.b).multiplyScalar(0.5)
      // O'lchamning O'ZI kameraga qarab ketgan (o'qi ko'rish yo'nalishiga 30°
      // dan yaqin): 3450 mm li chuqurlik orqadan qaraganda 2460 mm li ustun
      // yonida qisqa tik chiziq bo'lib, mijozni chalg'itardi. model-viewer ham
      // kameraga teskari tomondagi o'lchamni yashiradi.
      const korish = orta.clone().sub(camera.position).normalize()
      if (new Vector3().crossVectors(ab, korish).length() < 0.5) continue
      // Eni yoki chuqurligi ekranda TIK ko'rinadi — mijoz uni bo'yi deb o'qiydi
      // (orqadan qaralganda pastki qirradagi 3450 mm li chuqurlik 2460 mm li
      // ustun yonida tik chiziq edi). Faqat kamera past (45° dan) bo'lsa:
      // tepadan qaralganda (reja) tik chuqurlik tabiiy, bo'yi u yerda yo'q.
      // Tanlangan detalniki (`tosiq` yo'q) bundan ozod: detal ajratilgan,
      // o'lchami kartochkada ham bor — u chalg'itmaydi.
      if (
        o.tosiq &&
        Math.abs(ab.y) < 0.9 &&
        Math.hypot(korish.x, korish.z) > 0.7
      ) {
        const p0 = ekranga(orta)
        const p1 = ekranga(orta.clone().add(new Vector3(0, 10, 0)))
        const tx = p1.x - p0.x
        const ty = p1.y - p0.y
        const tik =
          Math.abs(tx * (b.y - a.y) - ty * (b.x - a.x)) /
          (Math.hypot(tx, ty) * piksel || 1e-6)
        if (tik < 0.42) continue
      }
      // Tik o'q bo'ylab masshtab ALOHIDA: bitta masshtab bilan oraliq burchakka
      // qarab 6-34 px bo'lardi (review'da o'lchandi)
      const m0 = ekranga(orta)
      const m1 = ekranga(orta.addScaledVector(o.n, 10))
      const tikPx = Math.hypot(m1.x - m0.x, m1.y - m0.y) / 10
      // Ekranda surilish yo'nalishi bilan o'lcham chizig'i orasidagi burchak
      // sinusi: kichik bo'lsa surilgan chiziq qirraning O'ZI ustiga tushadi
      // (gorizontga yaqin kamerada tepa yuzaning ikki o'qi deyarli bitta
      // gorizontal chiziqqa proyeksiyalanadi)
      const sinus =
        Math.abs(
          ((b.x - a.x) * (m1.y - m0.y) - (b.y - a.y) * (m1.x - m0.x)) / piksel,
        ) / Math.max(10 * tikPx, 1e-9)
      // Tomon deyarli yonidan ko'rinadi — surilgan chiziq qirra ustiga tushardi:
      // tik o'q o'lcham o'qidan 5 barobar ko'p qisqargan yoki ekranda undan 20°
      // dan kam og'gan. NISBIY: ilgari qat'iy 0.05 px/mm edi va telefonda butun
      // oshxona ko'rinib turganda to'g'ri qaralgan yuzalarning o'lchami ham
      // yo'qolardi. Bazischi o'lchamida surish fayldan — u tashlanmaydi,
      // strelkalar baribir ekranga tik ochiladi.
      if (o.surish === null && (tikPx * mmPx < 0.2 || sinus < 0.35)) continue
      const mmTik = 1 / Math.max(tikPx, 1e-6)
      // Qirradan ekranda TIK masofa `cheti` px: og'ma yo'nalishda uzunroq surish
      const surish = o.surish ?? (o.cheti * mmTik) / Math.max(sinus, 0.35)
      const A = o.a.clone().addScaledVector(o.n, surish)
      const B = o.b.clone().addScaledVector(o.n, surish)
      const As = ekranga(A)
      const Bs = ekranga(B)
      if (!As.oldinda || !Bs.oldinda) continue
      // Yorliq strelkalarni yopmasin: markazidan har uchigacha yarim eni + 10 px
      const L = Math.hypot(Bs.x - As.x, Bs.y - As.y)
      // Boshqa o'lcham uchi shu yerda: yo'nalishi boshqa bo'lsa ikki strelka
      // bitta burchakda "V" bo'lib qolardi (60 ko'rinishda 1-4 juft), bir
      // chiziqda bo'lsa — biri ikkinchisining ustiga tushadi (yondan qaralganda
      // qisqargan eni bo'yining ustida). Uchma-uch zanjir (bazischining
      // 300 | 300 i) — odatiy, u o'tkaziladi.
      const ux = (Bs.x - As.x) / Math.max(L, 1e-6)
      const uy = (Bs.y - As.y) / Math.max(L, 1e-6)
      const ustma = uchlar.some((q) => {
        const yaqin = [As, Bs].some((p) =>
          [q.a, q.b].some((r) => Math.hypot(p.x - r.x, p.y - r.y) < 10),
        )
        if (!yaqin) return false
        // Zanjir faqat bir 3D o'q bo'ylab: yondan qaralganda eni va bo'yi
        // ekranda bitta tik chiziqqa tushishi mumkin — ular zanjir emas
        if (Math.abs(q.yon.dot(ab)) < 0.99) return true
        const qL = Math.hypot(q.b.x - q.a.x, q.b.y - q.a.y) || 1e-6
        const qx = (q.b.x - q.a.x) / qL
        const qy = (q.b.y - q.a.y) / qL
        if (Math.abs(qx * uy - qy * ux) > 0.17) return true
        const t = [q.a, q.b].map((r) => (r.x - As.x) * ux + (r.y - As.y) * uy)
        return Math.min(L, Math.max(...t)) - Math.max(0, Math.min(...t)) > 4
      })
      if (ustma) continue
      const chet = lw / 2 + 10
      if (L < 2 * chet) continue
      const joy = YORLIQ_JOYI.map((t) => ({
        t,
        x: As.x + (Bs.x - As.x) * t - lw / 2,
        y: As.y + (Bs.y - As.y) * t - lh / 2,
        w: lw,
        h: lh,
      })).find(
        (r) =>
          r.t * L >= chet &&
          (1 - r.t) * L >= chet &&
          r.x >= bo.x0 &&
          r.y >= bo.y0 &&
          r.x + r.w <= bo.x1 &&
          r.y + r.h <= bo.y1 &&
          qabul.every(
            (q) =>
              r.x > q.x + q.w + 4 ||
              q.x > r.x + r.w + 4 ||
              r.y > q.y + q.h + 4 ||
              q.y > r.y + r.h + 4,
          ) &&
          !(o.tosiq && tosilgan(A.clone().lerp(B, r.t))),
      )
      if (!joy) continue
      qabul.push(joy)
      // Strelkalar ham band: keyingi o'lchamning yorlig'i ularni yopmasin
      for (const u of [As, Bs])
        qabul.push({ x: u.x - 5, y: u.y - 5, w: 10, h: 10 })
      uchlar.push({
        a: { x: As.x, y: As.y },
        b: { x: Bs.x, y: Bs.y },
        yon: ab.clone(),
      })
      s.style.transform = `translate3d(${joy.x}px, ${joy.y}px, 0)`
      s.style.visibility = "visible"
      // `yon` bo'ylab `P` nuqtada ekranda `px` bo'ladigan 3D vektor — o'sha
      // nuqtaning O'Z masshtabi bilan. Ilgari butun chiziqning o'rtacha
      // masshtabi olinardi va perspektivada bir o'lchamning ikki strelkasi
      // 6.5 px gacha farq qilardi (60 ko'rinishda o'lchandi). Yo'nalish
      // kameraga qarab qisqarsa (bazischi o'lchami kameraga surilgan) — 3D da
      // metrlab chiqib ketmasin.
      const pikselda = (P: Vector3, yon: Vector3, px: number) => {
        const p0 = ekranga(P)
        const p1 = ekranga(P.clone().addScaledVector(yon, 10))
        const mm =
          (10 * px) / Math.max(Math.hypot(p1.x - p0.x, p1.y - p0.y), 1e-3)
        return yon.clone().multiplyScalar(Math.min(mm, 10 * px * mmPx))
      }
      // Uzatma chiziq obyektdan TIRQISH bilan: tirqishsiz u panel qirrasining
      // davomi bo'lib, burchak "sinib chiqqan" qirradek o'qilardi (egasining
      // shikoyati). Chizmachilik standartlari (ASME, NKBA, US Navy) aynan shu
      // uchun tirqish qo'yadi. Surilishsiz o'lchamda (`Length` 0) uzatma yo'q.
      const chiziq = (p: Vector3, q: Vector3) =>
        chiziqlar.push(p.x, p.y, p.z, q.x, q.y, q.z)
      if (surish / mmTik > TIRQISH + 1)
        for (const [P, Q] of [
          [o.a, A],
          [o.b, B],
        ])
          chiziq(
            P.clone().add(pikselda(P, o.n, TIRQISH)),
            Q.clone().add(pikselda(Q, o.n, OSHISH)),
          )
      chiziq(A, B)
      // Uchlarida uzatma chiziqqa tiralgan STRELKA. Ilgari 45° qiya belgi edi —
      // u uzatma chiziq bilan kesishib, burilganda "×" bo'lib ko'rinardi. Qanotlar
      // EKRANGA tik tekislikda: `n` bo'ylab ochilsa, `n` kameraga qaraganda
      // strelka chiziq ustiga yopishib qolardi.
      for (const [P, ichkari] of [
        [A, ab],
        [B, ab.clone().negate()],
      ] as const) {
        const uz = pikselda(P, ichkari, STRELKA)
        const en = pikselda(
          P,
          new Vector3()
            .crossVectors(ab, camera.position.clone().sub(P))
            .normalize(),
          STRELKA_ENI,
        )
        chiziq(P, P.clone().add(uz).add(en))
        chiziq(P, P.clone().add(uz).sub(en))
      }
      return true
    }
    return false
  }

  /** Nomzodlar, keyin o'shalarning o'zi `TOR_CHETI` bilan */
  const torga = (g: Olcham[]): Olcham[] => [
    ...g,
    ...g.map((o) => ({ ...o, cheti: TOR_CHETI })),
  ]

  /** D1: tanlangan nusxaning eni va bo'yi — har biri ikki qirra variantida
   * (eni avval ekranda PASTDAGI qirrada, bo'yi O'NGDAGIsida) */
  const tanlanganOlcham = (i: number): Olcham[][] => {
    const mesh = meshes[i] as Mesh
    const bb = mesh.geometry.boundingBox
    const panel = panels[i]
    if (!bb) return []
    const M = mesh.matrixWorld
    // Kameraga qaragan yuza; chiziq undan 0.5 mm oldinda — panel bilan titramasin
    const yuzaMarkazi = new Vector3(
      (bb.min.x + bb.max.x) / 2,
      (bb.min.y + bb.max.y) / 2,
      bb.max.z,
    ).applyMatrix4(M)
    const oldinda =
      new Vector3(0, 0, 1)
        .transformDirection(M)
        .dot(camera.position.clone().sub(yuzaMarkazi)) > 0
    const z = oldinda ? bb.max.z + 0.5 : bb.min.z - 0.5
    const nuqta = (x: number, y: number) => new Vector3(x, y, z).applyMatrix4(M)
    const tomon = (x: number, y: number) =>
      new Vector3(x, y, 0).transformDirection(M)
    const eni = [bb.min.y, bb.max.y].map((c, j) => ({
      qiymat: panel.s[0],
      a: nuqta(bb.min.x, c),
      b: nuqta(bb.max.x, c),
      n: tomon(0, j ? 1 : -1),
      surish: null,
      cheti: OLCHAM_CHETI,
      tosiq: false,
    }))
    const boyi = [bb.min.x, bb.max.x].map((c, j) => ({
      qiymat: panel.s[1],
      a: nuqta(c, bb.min.y),
      b: nuqta(c, bb.max.y),
      n: tomon(j ? 1 : -1, 0),
      surish: null,
      cheti: OLCHAM_CHETI,
      tosiq: false,
    }))
    const tartib = (o: Olcham, ox: "x" | "y") => {
      const e = ekranga(o.a.clone().add(o.b).multiplyScalar(0.5))
      return ox === "x" ? -e.y : -e.x
    }
    return [
      eni.sort((p, q) => tartib(p, "x") - tartib(q, "x")),
      boyi.sort((p, q) => tartib(p, "y") - tartib(q, "y")),
    ].map(torga)
  }

  /** Bazischining o'lchami dunyo fazosida (guruh faqat siljigan) */
  const bazisdan = (d: (typeof bazisOlcham)[number]): Olcham => {
    const sur = d.o.length()
    const ab = d.b.clone().sub(d.a)
    // Surilishsiz o'lcham (`Length` 0, 460 faylda 9 ta, 8 tasi TIK): yo'nalish
    // chiziqqa tik bo'lishi shart — tik chiziqda Y bilan vektor ko'paytma nol
    // bo'lib, uzatma chiziq va strelka o'lcham chizig'ining o'ziga tushardi
    const tayanch =
      Math.abs(ab.clone().normalize().y) > 0.9
        ? new Vector3(0, 0, 1)
        : new Vector3(0, 1, 0)
    const n =
      sur >= 1
        ? d.o.clone().divideScalar(sur)
        : new Vector3().crossVectors(ab, tayanch).normalize()
    return {
      qiymat: d.v,
      a: d.a.clone().add(group.position),
      b: d.b.clone().add(group.position),
      n,
      surish: sur >= 1 ? sur : 0,
      cheti: 0,
      tosiq: true,
    }
  }

  /** Kamera gabarit markazining qaysi tomonida — har o'q uchun ±1, SUSTLIK
   * bilan: markazdan gabaritning 5% idan ko'proq o'tgandagina almashadi, aks
   * holda markaz yonida aylantirganda o'lcham u qirradan bu qirraga sakrardi */
  const gabaritTomon = new Vector3(1, 1, 1)

  /** D2: gabaritning uch o'lchami — ekranga qarab qirra tanlanadi. Har o'lcham
   * mahsulotning YUZASI tekisligida, bitta dunyo o'qi bo'ylab surilgan
   * (chizmachilikda: "o'lcham o'lchanayotgan yuza tekisligida yotadi" — US Navy
   * izometrik qoidasi, ISO 16792). Ilgari eni va chuqurligi 45° diagonalga
   * surilardi: uzatma chizig'i hech bir qirraga parallel bo'lmay, burchakdan
   * "sinib" chiqqan qirradek ko'rinardi. Bitta burchakka tegadigan ikki o'lcham
   * HECH QACHON bir o'q bo'ylab surilmaydi — aks holda ikkala strelka bitta
   * pikselga tushardi. Har birining zaxira varianti bor: birinchisi yonidan
   * ko'rinsa (`chiz`) keyingisi olinadi.
   *
   * Qirra — gabarit qutisiniki emas, mahsulotdagi HAQIQIY chiziq
   * (`gabaritQirralari`): U oshxonada eni orqa devor qatorida, chuqurligi yon
   * qatorda — old tomondagi havo ustida emas. Kameraga yaqin chorakda bunday
   * chiziq bo'lmasa keyingi chorak olinadi; o'qning hech bir choragida
   * bo'lmasa — quti qirrasi (ilgarigidek). */
  const gabaritOlcham = (): Olcham[][] => {
    if (gabaritQuti.isEmpty()) return []
    const q = gabaritQuti.clone().translate(group.position)
    const m = q.getCenter(new Vector3())
    const olchami = q.getSize(new Vector3())
    for (const k of ["x", "y", "z"] as const) {
      const d = camera.position[k] - m[k]
      if (Math.abs(d) > 0.05 * olchami[k]) gabaritTomon[k] = d > 0 ? 1 : -1
    }
    const { x: cx, y: cy, z: cz } = gabaritTomon
    // Odatda kamera yuqoridan qaraydi: eni va chuqurligi YUQORI qirrada —
    // ko'rinadigan burchakdan. Pastki qirrada uzatma chiziq pol sathidagi
    // xayoliy burchakdan chiqardi: tsokol ichkariga kirgan, oyoqlari bor
    // mebelda o'lcham mebelga emas, polga bog'langandek ko'rinardi
    // (`02 tumba`). Pastdan qaralsa — pastki qirra.
    const [W, H, D] = gabaritQiymat
    const kam = [q.min.x, q.min.y, q.min.z]
    const kop = [q.max.x, q.max.y, q.max.z]
    const sil = [group.position.x, group.position.y, group.position.z]
    /** `ox` o'qiga parallel chiziq, `su`/`sv` chorakda (o'qqa tik ikki o'q
     * tartibida) — haqiqiysi, u o'qda umuman yo'q bo'lsa quti qirrasi */
    const qirra = (ox: number, su: number, sv: number) => {
      const [u, v] = [0, 1, 2].filter((k) => k !== ox)
      const c = gabaritQirra[ox][(su > 0 ? 1 : 0) + (sv > 0 ? 2 : 0)]
      if (!c && gabaritQirra[ox].some(Boolean)) return null
      const cu = c ? c[0] + sil[u] : su > 0 ? kop[u] : kam[u]
      const cv = c ? c[1] + sil[v] : sv > 0 ? kop[v] : kam[v]
      const nuqta = (t: number) => {
        const p = [0, 0, 0]
        p[ox] = t
        p[u] = cu
        p[v] = cv
        return new Vector3(p[0], p[1], p[2])
      }
      return { a: nuqta(kam[ox]), b: nuqta(kop[ox]) }
    }
    const olchamlar = (
      qiymat: number,
      ox: number,
      choraklar: [number, number, Vector3[]][],
    ): Olcham[] =>
      choraklar.flatMap(([su, sv, yonlar]) => {
        const c = qirra(ox, su, sv)
        return c
          ? yonlar.map((n) => ({
              qiymat,
              a: c.a,
              b: c.b,
              n,
              surish: null,
              cheti: GABARIT_CHETI,
              tosiq: true,
              // Mijoz ham ko'radi: raqam birligi bilan (model-viewer, Roomle)
              matn: `${matni(qiymat)} mm`,
            }))
          : []
      })
    const v = (x: number, y: number, z: number) => new Vector3(x, y, z)
    // Choraklar kameraga yaqinidan. Burchakni bo'lishadigan o'lchamlar turli
    // o'qqa surilishi uchun: eni tepaga (keyin oldinga), chuqurligi yonga
    // (pastki chorakda pastga ham), bo'yi yaqin tomonda faqat oldinga — u
    // yerda chuqurlik yonga surilgan.
    return [
      olchamlar(W, 0, [
        [cy, cz, [v(0, cy, 0), v(0, 0, cz)]],
        [cy, -cz, [v(0, cy, 0), v(0, 0, -cz)]],
        [-cy, cz, [v(0, -cy, 0), v(0, 0, cz)]],
        [-cy, -cz, [v(0, -cy, 0), v(0, 0, -cz)]],
      ]),
      olchamlar(H, 1, [
        [-cx, cz, [v(-cx, 0, 0), v(0, 0, cz)]],
        [cx, -cz, [v(0, 0, -cz), v(cx, 0, 0)]],
        [cx, cz, [v(0, 0, cz)]],
        [-cx, -cz, [v(-cx, 0, 0), v(0, 0, -cz)]],
      ]),
      olchamlar(D, 2, [
        [cx, cy, [v(cx, 0, 0)]],
        [-cx, cy, [v(-cx, 0, 0)]],
        [cx, -cy, [v(cx, 0, 0), v(0, -cy, 0)]],
        [-cx, -cy, [v(-cx, 0, 0), v(0, -cy, 0)]],
      ]),
    ]
      .filter((g) => g.length > 0 && g[0].qiymat > 0)
      .map(torga)
  }

  /** Kadr bilan birga. `tinch` — kamera, eshiklar va tween turibdi: faqat shunda
   * D1+ va D2 (nur bilan) joylanadi, aks holda ular yashirin. */
  const olchamYangila = (tinch: boolean) => {
    const w = canvas.clientWidth
    const h = canvas.clientHeight
    // Yorliq uchun bo'sh joy: tugmalar qatori va pastki panel (kartochka +
    // qidiruv) dan tashqari
    const bo = {
      x0: 8,
      y0: yorliqZona.ust,
      x1: w - 8,
      y1: h - Math.max(yorliqZona.past, band + 8),
    }
    const tanlov = [...tanlangan].filter(
      (i) => i < panels.length && meshes[i] instanceof Mesh,
    )
    camera.updateMatrixWorld()
    // Faqat tanlangan nusxalar va ularning otasi — butun mahsulotni har kadrda
    // qayta hisoblash shart emas (render baribir o'zi yangilaydi)
    for (const i of tanlov) meshes[i].updateWorldMatrix(true, false)
    const royxat: Olcham[][] = []
    if (tanlov.length) {
      const markazdan = (i: number) => {
        const b = (meshes[i] as Mesh).geometry.boundingBox
        if (!b) return Number.POSITIVE_INFINITY
        const e = ekranga(
          b.getCenter(new Vector3()).applyMatrix4(meshes[i].matrixWorld),
        )
        return Math.hypot(e.x - (bo.x0 + bo.x1) / 2, e.y - (bo.y0 + bo.y1) / 2)
      }
      let eng = tanlov[0]
      let engM = Number.POSITIVE_INFINITY
      for (const i of tanlov) {
        const d = markazdan(i)
        if (d < engM) {
          eng = i
          engM = d
        }
      }
      if (
        !tanlov.includes(olchamNusxa) ||
        markazdan(olchamNusxa) > engM * 1.2 + 1
      )
        olchamNusxa = eng
      royxat.push(...tanlanganOlcham(olchamNusxa))
    } else olchamNusxa = -1

    const ajratilgan = explode > 0 || ajratish.ga > 0
    if (tinch && !ajratilgan && qatlam) {
      // Ochiq birlik ichidagi o'lcham (eshikka yozilgani) yopiq holatda yozilgan —
      // eshik ochilganda u havoda qolardi
      const ochiq = new Set<number>()
      birlik.forEach((b, i) => {
        if (b !== null && ochiqlik[i] > 0) ochiq.add(b)
      })
      const bazis = bazisOlcham.filter(
        (d) => d.g === undefined || !ochiq.has(d.g),
      )
      tosuvchilar.length = 0
      meshes.forEach((m, i) => {
        const holat = holatFor(i)
        if (xona.has(i) || shaffof.has(i) || holat === "xira") return
        // Kontur va qo'shni — shaffof, chiziqni to'smaydi
        if (holat === "kontur" || holat === "qoshni") return
        tosuvchilar.push(m)
      })
      if (tanlov.length) {
        // D1+: uchi tanlangan detalning (istalgan nusxasi) YOPIQ qutisidan 1 mm ichida
        const qutilar = tanlov.map((i) => {
          const b = ((meshes[i] as Mesh).geometry.boundingBox as Box3)
            .clone()
            .expandByScalar(1)
          const teskari = new Matrix4()
            .compose(asl[i], aslQuat[i], new Vector3(1, 1, 1))
            .invert()
          return { b, teskari }
        })
        const tegadi = (p: Vector3) =>
          qutilar.some(({ b, teskari }) =>
            b.containsPoint(p.clone().applyMatrix4(teskari)),
          )
        for (const d of bazis)
          if (tegadi(d.a) || tegadi(d.b)) royxat.push([bazisdan(d)])
      } else if (olchamlarYoniq && !topilgan.size) {
        royxat.push(...gabaritOlcham())
        for (const d of [...bazis].sort((p, q) => q.v - p.v))
          royxat.push([bazisdan(d)])
      }
    }

    const qabul: Joy[] = []
    const chiziqlar: number[] = []
    const uchlar: Uch[] = []
    let k = 0
    for (const nomzodlar of royxat)
      if (chiz(nomzodlar, k, bo, qabul, chiziqlar, uchlar)) k++
    for (let j = k; j < yorliqlar.length; j++)
      yorliqlar[j].style.visibility = "hidden"
    olchamChiziq.geometry.dispose()
    olchamChiziq.geometry = new BufferGeometry()
    olchamChiziq.geometry.setAttribute(
      "position",
      new Float32BufferAttribute(chiziqlar, 3),
    )
    olchamChiziq.visible = chiziqlar.length > 0
  }

  const resize = () => {
    const { clientWidth: w, clientHeight: h } = canvas
    if (!w || !h) return
    renderer.setSize(w, h, false)
    proyeksiya()
    // Telefon portretdan landshaftga burilganda gorizontal burchak torayadi
    // va model chetidan kesilib qolardi. Foydalanuvchining BURCHAGI
    // saqlanadi — faqat masofa yetarli darajada uzaytiriladi. Ilgari bu
    // faqat "foydalanuvchi kameraga tegmagan" bo'lsa ishlardi, ya'ni bir
    // marta aylantirgandan keyin burilish modelni kesib qo'yardi.
    if (meshes.length) {
      const v = camera.position.clone().sub(controls.target)
      const kerak = Math.min(
        kerakliMasofa(v.clone().normalize()),
        controls.maxDistance,
      )
      if (v.length() < kerak) {
        camera.position
          .copy(controls.target)
          .addScaledVector(v.normalize(), kerak)
        controls.update()
      }
    }
    belgila()
  }
  const observer = new ResizeObserver(resize)
  observer.observe(canvas)
  resize()

  let frame = 0
  let oldingiTinch = false
  const oldingiKamera = { pos: new Vector3(), q: new Quaternion() }
  const tick = () => {
    frame = requestAnimationFrame(tick)
    // `update()` kamera o'zgarganda `true` qaytaradi (susayish tugaguncha ham).
    // Qimirlamagan sahnani qayta chizish telefon batareyasini bekorga yeydi.
    let ozgardi = controls.update()
    // Barmoq tomon yaqinlashtirilgan nishon uzoqlashganda (sig'dirish
    // masofasining 85% idan) asta mahsulot markaziga qaytadi — surish o'chiq
    // qarori (mahsulot markazda) butun mahsulot ko'ringanda saqlanadi
    const uzoqlik = camera.position.distanceTo(controls.target)
    if (
      !tweenHarakatda &&
      !fokusdanOldin &&
      uzoqlik > 0.85 * sigdirMasofa &&
      controls.target.distanceToSquared(fokus) > 1
    ) {
      const t = Math.min(
        1,
        (uzoqlik - 0.85 * sigdirMasofa) / (0.3 * sigdirMasofa),
      )
      const siljit = fokus.clone().sub(controls.target).multiplyScalar(t)
      controls.target.add(siljit)
      camera.position.add(siljit)
      ozgardi = true
    }
    // Kamera shu kadrda qancha siljidi — piksel ulushida. `update()` ning o'zi
    // yetmaydi: g'ildirak va ikki barmoqli zoom `update()` ni hodisa ichida
    // chaqiradi (bu yerdagisi `false` qaytaradi), susayish dumi esa ko'rinmas
    // sub-piksel siljish bilan ~1 s `true` qaytarib turadi.
    const masofa = camera.position.distanceTo(controls.target) || 1
    const siljish =
      camera.position.distanceTo(oldingiKamera.pos) / masofa +
      camera.quaternion.angleTo(oldingiKamera.q)
    oldingiKamera.pos.copy(camera.position)
    oldingiKamera.q.copy(camera.quaternion)
    if (ozgardi && siljish < 1e-4) {
      // Susayish dumi — ko'zga ko'rinmaydi: to'xtatamiz, o'lchamlar kechikmasin
      controls.enableDamping = false
      controls.update()
      controls.enableDamping = true
      ozgardi = false
    }
    // Tinchlikka o'tgan (yoki undan chiqqan) kadr ham chiziladi: og'ir o'lchamlar
    // shunda joylanadi yoki yashiriladi
    const tinch =
      siljish < 1e-4 &&
      !ozgardi &&
      !pozaHarakatda &&
      !tweenHarakatda &&
      !bandHarakatda
    if (tinch !== oldingiTinch) {
      oldingiTinch = tinch
      kir = true
    }
    if (ozgardi || kir) {
      // Yorliqlar AYNAN shu kadr bilan: alohida sikl batareyani yerdi
      olchamYangila(tinch)
      renderer.render(scene, camera)
      kir = false
    }
  }
  tick()

  return {
    load,
    setSelected,
    setFound,
    setPose,
    focusOn,
    nishonniQaytar,
    resetView,
    setPastkiBand,
    setOlchamlar: (yoniq: boolean) => {
      olchamlarYoniq = yoniq
      belgila()
    },
    setIchki: (yoniq: boolean) => {
      ichkiKorinish = yoniq
      applyStates()
    },
    setYorliqZona: (ust: number, past: number) => {
      Object.assign(yorliqZona, { ust, past })
      belgila()
    },
    dispose: () => {
      cancelAnimationFrame(frame)
      cancelAnimationFrame(tweenFrame)
      cancelAnimationFrame(bandFrame)
      cancelAnimationFrame(harakatFrame)
      observer.disconnect()
      canvas.removeEventListener("pointerdown", onDown)
      canvas.removeEventListener("pointerup", onUp)
      canvas.removeEventListener("pointercancel", onCancel)
      clear()
      controls.dispose()
      soya.geometry.dispose()
      ;(soya.material as MeshBasicMaterial).dispose()
      soyaTex.dispose()
      muhit.texture.dispose()
      pmrem.dispose()
      qirraMat.dispose()
      qirraOchMat.dispose()
      konturMat.dispose()
      fonQirraMat.dispose()
      tanlanganQirraMat.dispose()
      olchamChiziq.geometry.dispose()
      olchamMat.dispose()
      for (const s of yorliqlar) s.remove()
      for (const t of teksturalar.values()) t.dispose()
      // `forceContextLoss()` YO'Q — u kanvasni butunlay o'ldiradi. React
      // StrictMode effektni ikki marta ishlatadi va ikkinchi `createScene`
      // O'SHA kanvasga kontekst so'raydi: brauzer `null` qaytarib, sahifa
      // "Xato" ekraniga tushardi (brauzerda o'lchandi).
      renderer.dispose()
    },
  }
}
