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
      socket = new WebSocket(url)
      socket.onopen = () => {
        setOnline(true)
        heartbeat = setInterval(
          () => socket?.readyState === 1 && socket.send("ping"),
          30_000,
        )
      }
      socket.onmessage = (e) => {
        try {
          const event = JSON.parse(e.data)
          if (event.type && event.type !== "pong") handler.current(event)
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
