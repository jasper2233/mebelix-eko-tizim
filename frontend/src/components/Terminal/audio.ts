// Audio signallari (TZ 8.4.3): sex shovqinida majburiy. WebAudio — lokal, internetga bog'liq emas.

let ctx: AudioContext | null = null

function beep(freq: number, durationMs: number, delayMs = 0) {
  ctx ??= new AudioContext()
  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.type = "square"
  osc.frequency.value = freq
  gain.gain.value = 0.15
  osc.connect(gain)
  gain.connect(ctx.destination)
  const start = ctx.currentTime + delayMs / 1000
  osc.start(start)
  osc.stop(start + durationMs / 1000)
}

export const playSuccess = () => beep(600, 100)
export const playError = () => beep(200, 500)
export const playWarning = () => {
  beep(800, 90)
  beep(800, 90, 180)
}
