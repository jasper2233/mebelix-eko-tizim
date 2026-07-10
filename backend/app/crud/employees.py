from app.crud.base import BaseCRUD
from app.models import Employee


class CRUDEmployee(BaseCRUD[Employee]):
    pass


crud_employees = CRUDEmployee(Employee)
