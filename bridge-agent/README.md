# MebeliX bridge-agent

Sex ichidagi yengil servis (TZ 2.2.2): masofaviy serverdan chop etish buyruqlarini olib,
GoDEX termo-printerga lokal tarmoqda yuboradi. Internet/printer uzilganda buyruqlar
`print-queue.jsonl` faylida saqlanadi va aloqa tiklangach avtomatik bajariladi.

## O'rnatish (sexdagi mini-PC yoki terminallardan biri)

```bash
pip install websockets
```

## Ishga tushirish

```bash
MES_URL=wss://app.mebelix.uz \
BRIDGE_TOKEN=<serverdagi BRIDGE_TOKEN> \
PRINTER_IP=192.168.1.90 \
python3 agent.py
```

Serverda `.env` ichida `BRIDGE_TOKEN` bir xil qiymatda bo'lishi shart
(`openssl rand -hex 24` bilan yarating).

## systemd (doimiy ishlash uchun)

```ini
# /etc/systemd/system/mebelix-bridge.service
[Unit]
Description=MebeliX bridge-agent
After=network-online.target

[Service]
Environment=MES_URL=wss://app.mebelix.uz
Environment=BRIDGE_TOKEN=CHANGE_ME
Environment=PRINTER_IP=192.168.1.90
WorkingDirectory=/opt/mebelix-bridge
ExecStart=/usr/bin/python3 agent.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Eslatma: SCX fayllar bridge orqali o'tmaydi — ular stanok kompyuterida brauzer orqali
yuklab olinadi (TZ 12.5).
