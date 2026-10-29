"""integratsiya moduli ochiq interfeysi — tashqaridan faqat shu fayl import qilinadi."""

from app.modules.integratsiya.katalog import sinxron as katalog_sinxron
from app.modules.integratsiya.kroy import KroyXato, enabled, ochish
from app.modules.integratsiya.outbox import yubor as outbox_yubor
from app.modules.integratsiya.sex import arra_skan

__all__ = ["KroyXato", "arra_skan", "enabled", "katalog_sinxron", "ochish", "outbox_yubor"]
