from app.models import BridgeAgent, Client, Employee, Machine, Post

from .audit import log_action
from .base import BaseCRUD
from .orders import crud_orders
from .users import crud_users

# Yupqa registrlar — o'z metodi yo'q, shuning uchun BaseCRUD to'g'ridan-to'g'ri.
# Modelga maxsus metod kerak bo'lsa — orders.py/users.py kabi alohida subclass qilinadi.
crud_bridge_agents: BaseCRUD[BridgeAgent] = BaseCRUD(BridgeAgent)
crud_clients: BaseCRUD[Client] = BaseCRUD(Client)
crud_employees: BaseCRUD[Employee] = BaseCRUD(Employee)
crud_machines: BaseCRUD[Machine] = BaseCRUD(Machine)
crud_posts: BaseCRUD[Post] = BaseCRUD(Post)

__all__ = [
    "crud_bridge_agents",
    "crud_clients",
    "crud_employees",
    "crud_machines",
    "crud_orders",
    "crud_posts",
    "crud_users",
    "log_action",
]
