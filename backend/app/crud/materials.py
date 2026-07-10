from app.crud.base import BaseCRUD
from app.models import Material


class CRUDMaterial(BaseCRUD[Material]):
    pass


crud_materials = CRUDMaterial(Material)
