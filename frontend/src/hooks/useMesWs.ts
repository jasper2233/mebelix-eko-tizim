// WebSocket ulanish (TZ 2.3): avto-reconnect, 30s heartbeat, online holati.

import { useEffect, useRef, useState } from "react"
import { API_BASE } from "@/utils"

type MesEvent = { type: string; payload: Record<string, unknown> }

export function useMesWs(onEvent: (event: MesEvent) => void) {
  const [online, setOnline] = useState(false)
  const handler = useRef(onEvent)
  handler.current = onEvent

  useEffect(() => {
    let socket: WebSocket | null = null
    let heartbeat: ReturnType<typeof setInterval> | null = null
    let reconnect: ReturnType<typeof setTimeout> | null = null
    let closed = false

    const connect = () => {
      const base = API_BASE || window.location.origin
      const url = `${base.replace(/^http/, "ws")}/api/v1/ws/events`
      // Server har "ping"ga {"type":"pong"} qaytaradi (api/routes/ws.py).
      // Javob KELMASA ulanish yarim-ochiq: TCP hali tirik ko'rinadi, lekin
      // birorta ham event yetib kelmaydi. Busiz `online` faqat onclose'da
      // o'chardi — indikator "JONLI" deb yolg'on gapirardi.
      let lastPongAt = Date.now()
      socket = new WebSocket(url)
      socket.onopen = () => {
        setOnline(true)
        lastPongAt = Date.now()
        heartbeat = setInterval(() => {
          if (socket?.readyState !== 1) return
          // Ikki davr pong'siz — soketni yopamiz, onclose reconnect qiladi
          if (Date.now() - lastPongAt > 75_000) socket.close()
          else socket.send("ping")
        }, 30_000)
      }
      socket.onmessage = (e) => {
        try {
          const event = JSON.parse(e.data)
          if (event.type === "pong") lastPongAt = Date.now()
          else if (event.type) handler.current(event)
        } catch {
          /* skip non-JSON frames */
        }
      }
      socket.onclose = () => {
        setOnline(false)
        if (heartbeat) clearInterval(heartbeat)
        if (!closed) reconnect = setTimeout(connect, 3000)
      }
      socket.onerror = () => socket?.close()
    }
    connect()

    return () => {
      closed = true
      if (heartbeat) clearInterval(heartbeat)
      if (reconnect) clearTimeout(reconnect)
      socket?.close()
    }
  }, [])

  return { online }
}
