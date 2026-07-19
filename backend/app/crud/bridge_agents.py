from app.crud.base import BaseCRUD
from app.models import BridgeAgent


class CRUDBridgeAgent(BaseCRUD[BridgeAgent]):
    pass


crud_bridge_agents = CRUDBridgeAgent(BridgeAgent)
