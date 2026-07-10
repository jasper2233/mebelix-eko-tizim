from app.crud.base import BaseCRUD
from app.models import Client


class CRUDClient(BaseCRUD[Client]):
    pass


crud_clients = CRUDClient(Client)
