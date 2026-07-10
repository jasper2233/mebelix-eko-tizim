from app.crud.base import BaseCRUD
from app.models import Post


class CRUDPost(BaseCRUD[Post]):
    pass


crud_posts = CRUDPost(Post)
