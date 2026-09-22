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
  CanvasTexture,
  DirectionalLight,
  DoubleSide,
  EdgesGeometry,
  ExtrudeGeometry,
  Group,
  LineBasicMaterial,
  LineSegments,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
  NeutralToneMapping,
  Path,
  PerspectiveCamera,
  PlaneGeometry,
  PMREMGenerator,
  Quaternion,
  Raycaster,
  Scene,
  Shape,
  Vector2,
  Vector3,
  WebGLRenderer,
} from "three"
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js"
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js"
import {
  type BazisModel,
  type BazisPanel,
  isGlass,
  materialColor,
  materialRoughness,
  XONA_YUZASI,
} from "./model"

/** Panelning ko'rinish holati. */
type Holat = "oddiy" | "xira" | "tanlangan" | "topilgan"

const RANG = {
  qirra: "#44546b",
  tanlangan: "#f0a52f",
  topilgan: "#2f496e",
}

export type PanelHit = { panel: BazisPanel; index: number } | null

export type SceneApi = {
  load: (model: BazisModel) => void
  setSelected: (indexes: number[]) => void
  setFound: (indexes: Set<number>) => void
  /** Ko'rinish holati: eshiklar ochiqligi va ajratilganlik, ikkalasi 0..1 */
  setPose: (ochiq: number, explode: number) => void
  focusOn: (index: number) => void
  /** Orbit markazini mahsulotga qaytaradi (detal tanlovi yopilganda) */
  nishonniQaytar: () => void
  resetView: () => void
  dispose: () => void
}

const shapeFor = (panel: BazisPanel): Shape | null => {
  if (panel.o.length < 3) return null
  const shape = new Shape(panel.o.map(([x, y]) => new Vector2(x, y)))
  for (const [cx, cy, r] of panel.c ?? []) {
    const hole = new Path()
    hole.absarc(cx, cy, r, 0, Math.PI * 2, true)
    shape.holes.push(hole)
  }
  return shape
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
  // 40 mm dan yaqinga hech narsa tushmaydi: `minDistance` 228 mm dan katta.
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
      const oyna = holat === "oddiy" && isGlass(nom)
      const xira = holat === "xira"
      m = new MeshStandardMaterial({
        color:
          holat === "tanlangan"
            ? RANG.tanlangan
            : holat === "topilgan"
              ? RANG.topilgan
              : materialColor(nom),
        roughness: materialRoughness(nom),
        metalness: 0,
        transparent: xira || oyna,
        // Xira: kontekst yo'qolmasin, lekin tanlangani ajralib tursin
        opacity: xira ? 0.16 : oyna ? 0.34 : 1,
        depthWrite: !xira && !oyna,
        side: DoubleSide,
      })
      materiallar.set(key, m)
    }
    return m
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
  /** Rangning nisbiy yorqinligi (sRGB). 0.18 dan pasti — quyuq dekor. */
  const yorugmi = (hex: string): boolean => {
    const n = Number.parseInt(hex.slice(1), 16)
    const k = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => {
      const c = v / 255
      return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
    })
    return 0.2126 * k[0] + 0.7152 * k[1] + 0.0722 * k[2] > 0.18
  }

  let meshes: Mesh[] = []
  /** Har panelning qirra chizig'i — xira holatda yashiriladi (pastda) */
  let qirralar: LineSegments[] = []
  let panels: BazisPanel[] = []
  let asl: Vector3[] = []
  let aslQuat: Quaternion[] = []
  /** Ochilgan holat — faqat harakatlanadigan panelda to'ladi */
  let ochiqPos: (Vector3 | null)[] = []
  let ochiqQuat: (Quaternion | null)[] = []
  let yonalish: Vector3[] = []
  /** Panel markazi — guruh koordinatalarida (fokus va ochish shundan) */
  let markazlar: Vector3[] = []
  const markaz = new Vector3()
  /** Kameraning nishoni va gabaritning yarmi — guruh siljitilgandan KEYINGI holat */
  const fokus = new Vector3()
  const yarimOlcham = new Vector3(500, 500, 500)
  let olcham = 1000
  let tanlangan = new Set<number>()
  let topilgan = new Set<number>()
  /** Xona yuzalari (devor, pol, kafel) — doim xira va bosilmaydi. */
  let xona = new Set<number>()
  let explode = 0
  /** Eshiklarning ochilganlik darajasi, 0..1 */
  let ochiq = 0
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
    if (tanlangan.has(i)) return "tanlangan"
    if (topilgan.size) return topilgan.has(i) ? "topilgan" : "xira"
    return tanlangan.size ? "xira" : "oddiy"
  }

  const applyStates = () => {
    meshes.forEach((mesh, i) => {
      const holat = holatFor(i)
      mesh.material = materialFor(panels[i].m, holat)
      // Xira panelning yuzasi deyarli yo'qoladi, lekin qirra chizig'i to'liq
      // kuchda qolsa tanlangan detal ustida "qafas" bo'lib turardi.
      qirralar[i].visible = holat !== "xira"
    })
    belgila()
  }

  const clear = () => {
    for (const mesh of meshes) {
      mesh.geometry.dispose()
      for (const child of mesh.children) {
        if (child instanceof LineSegments) child.geometry.dispose()
      }
    }
    group.clear()
    // Materiallar model bo'yicha (oyna indekslari almashadi) — eskilarini
    // tashlab ketsak GPU xotirasi mahsulot almashtirgan sayin o'sardi.
    for (const m of materiallar.values()) m.dispose()
    materiallar.clear()
    meshes = []
    qirralar = []
    panels = []
    asl = []
    aslQuat = []
    ochiqPos = []
    ochiqQuat = []
    yonalish = []
    markazlar = []
    tanlangan = new Set()
    // Holat ham tiklanadi: busiz yangi mahsulot eski modelning ochilganligini
    // va qidiruv natijasini meros qilib olardi.
    topilgan = new Set()
    xona = new Set()
    ochiq = 0
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
    })
    const quti = new Box3()
    for (const [i, panel] of model.panels.entries()) {
      const shape = shapeFor(panel)
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
      markazlar.push(b.getCenter(new Vector3()))
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
    ochiqPos = model.panels.map((p) =>
      p.po ? new Vector3().fromArray(p.po) : null,
    )
    ochiqQuat = model.panels.map((p) =>
      p.qo ? new Quaternion().fromArray(p.qo) : null,
    )
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
   * uchun masofa keskin qisqartirilmaydi. */
  const focusOn = (index: number) => {
    const mesh = meshes[index]
    if (!mesh) return
    // Markaz JORIY pozadan olinadi, `load` dagi yopiq holatdan emas: eshiklar
    // ochiq yoki panellar ajratilgan bo'lsa detal yarim metrgacha siljigan
    // bo'ladi va kamera bo'sh joyga uchib borardi.
    const qayerda = new Box3().setFromObject(mesh).getCenter(new Vector3())
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
    if (controls.target.distanceToSquared(fokus) < 1 && !fokusdanOldin) return
    const bosh = controls.target.clone()
    const yonalish = camera.position.clone().sub(controls.target).normalize()
    const d0 = camera.position.distanceTo(controls.target)
    const d1 = fokusdanOldin || d0
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
   * yopiq va ochiq holat orasida interpolyatsiya. Ajratish — sun'iy: panel
   * mahsulot markazidan tashqariga suriladi. */
  const joylash = () => {
    meshes.forEach((mesh, i) => {
      const po = ochiqPos[i]
      const qo = ochiqQuat[i]
      if (ochiq > 0 && po && qo) {
        mesh.position.lerpVectors(asl[i], po, ochiq)
        mesh.quaternion.slerpQuaternions(aslQuat[i], qo, ochiq)
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

  /** Ko'rinish holati: eshiklar ochiqligi va ajratilganlik BIRGA beriladi.
   *
   * Ikkitasi alohida chaqirilganda har kadrda butun panel massivi IKKI marta
   * aylanardi va kamera masofasi ikki joyda hisoblanardi. Masofa endi
   * eslab qolinmaydi — JORIY masofa nisbat bilan kengaytiriladi, shuning
   * uchun foydalanuvchining zoom'i har doim saqlanadi (ilgari ochiq holatda
   * qilingan zoom keyingi almashuvda bekor bo'lardi). */
  const setPose = (yangiOchiq: number, yangiExplode: number) => {
    const eski = kengayish(ochiq, explode)
    const yangi = kengayish(yangiOchiq, yangiExplode)
    ochiq = yangiOchiq
    explode = yangiExplode
    joylash()
    if (yangi === eski) return
    const v = camera.position.clone().sub(controls.target)
    const d = Math.min(
      Math.max((v.length() * yangi) / eski, controls.minDistance),
      controls.maxDistance,
    )
    camera.position.copy(controls.target).addScaledVector(v.normalize(), d)
  }

  const setSelected = (indexes: number[]) => {
    tanlangan = new Set(indexes)
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
  /** Ekrandagi barmoqlar soni. IKKI barmoq — bu pinch, tanlash EMAS. */
  let barmoq = 0

  const onDown = (e: PointerEvent) => {
    barmoq++
    if (barmoq > 1) {
      // Ikkinchi barmoq tushdi: bu pinch. Busiz uning `pointerup` i o'z
      // tushgan nuqtasidan 8 px narida bo'lgani uchun "bosish" deb
      // hisoblanib, tanlangan detalni YO'QOTARDI (telefonda takrorlandi).
      bosildi = false
      return
    }
    bosh.set(e.clientX, e.clientY)
    bosildi = true
  }
  const onUp = (e: PointerEvent) => {
    barmoq = Math.max(0, barmoq - 1)
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
    // ko'rmagan detalini tanlab olardi.
    const nishon = topilgan.size
      ? meshes.filter((_, i) => topilgan.has(i))
      : meshes.filter((_, i) => !xona.has(i))
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

  // --- o'lcham va kadr ---
  const resize = () => {
    const { clientWidth: w, clientHeight: h } = canvas
    if (!w || !h) return
    renderer.setSize(w, h, false)
    camera.aspect = w / h
    camera.updateProjectionMatrix()
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
  const tick = () => {
    frame = requestAnimationFrame(tick)
    // `update()` kamera o'zgarganda `true` qaytaradi (susayish tugaguncha ham).
    // Qimirlamagan sahnani qayta chizish telefon batareyasini bekorga yeydi.
    const ozgardi = controls.update()
    if (ozgardi || kir) {
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
    dispose: () => {
      cancelAnimationFrame(frame)
      cancelAnimationFrame(tweenFrame)
      observer.disconnect()
      canvas.removeEventListener("pointerdown", onDown)
      canvas.removeEventListener("pointerup", onUp)
      clear()
      controls.dispose()
      soya.geometry.dispose()
      ;(soya.material as MeshBasicMaterial).dispose()
      soyaTex.dispose()
      muhit.texture.dispose()
      pmrem.dispose()
      qirraMat.dispose()
      qirraOchMat.dispose()
      // `forceContextLoss()` YO'Q — u kanvasni butunlay o'ldiradi. React
      // StrictMode effektni ikki marta ishlatadi va ikkinchi `createScene`
      // O'SHA kanvasga kontekst so'raydi: brauzer `null` qaytarib, sahifa
      // "Xato" ekranига tushardi (brauzerda o'lchandi).
      renderer.dispose()
    },
  }
}
