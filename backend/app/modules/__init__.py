"""EKO TIZIM modullari (TZ §2.1) — modulli monolit.

Har modul o'z papkasida, keyinroq o'z Postgres sxemasida. Qoidalar:

1. Modul tashqarisidagi kod (ishlab chiqarish, boshqa modul) modulga FAQAT uning
   `service` qismi orqali murojaat qiladi: `from app.modules.ombor import service`.
   Ichki `models`, `repo` va hokazo — modulning shaxsiy ishi.
2. Bitta tranzaksiyada bo'lishi shart amallar uchun servis funksiyasi chaqiruvchining
   `AsyncSession` ini qabul qiladi va o'zi `commit` qilmaydi.
3. Kechikishi mumkin bo'lgan oqibat — `integratsiya` outbox'i orqali.

Chegara `scripts/check_module_boundaries.py` bilan tekshiriladi (`make lint`).
"""
