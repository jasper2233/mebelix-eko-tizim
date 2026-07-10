from app.crud.base import BaseCRUD
from app.models import Machine


class CRUDMachine(BaseCRUD[Machine]):
    pass


crud_machines = CRUDMachine(Machine)
