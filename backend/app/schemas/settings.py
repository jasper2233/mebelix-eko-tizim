from pydantic import BaseModel, Field


class SystemSettingRead(BaseModel):
    key: str
    value: str


class SystemSettingUpdate(BaseModel):
    #: Bo'sh qiymat — qoidani o'chirish (nostandart belgisi uchun: hech bir detal
    #: avtomatik belgilanmaydi). 8 belgi yetadi: bu suffiks, nom emas.
    value: str = Field(max_length=8)
