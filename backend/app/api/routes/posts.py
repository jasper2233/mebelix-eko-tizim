from fastapi import APIRouter, Request
from sqlalchemy import select

from app.api.deps import AdminUser, CurrentUser, SessionDep, client_ip
from app.crud import crud_posts, log_action
from app.models import Post
from app.schemas.posts import PostRead, PostUpdate

router = APIRouter(prefix="/posts", tags=["posts"])


@router.get("/", response_model=list[PostRead], operation_id="read_posts")
async def read_posts(db: SessionDep, _: CurrentUser) -> list[Post]:
    rows = (
        (await db.execute(select(Post).where(Post.is_deleted == False).order_by(Post.order_index)))  # noqa: E712
        .scalars()
        .all()
    )
    return list(rows)


@router.patch("/{post_id}", response_model=PostRead, operation_id="update_post")
async def update_post(
    db: SessionDep, current_user: AdminUser, post_id: int, body: PostUpdate, request: Request
) -> Post:
    post = await crud_posts.get_or_404(db, "Post topilmadi.", id=post_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(post, field, value)
    log_action(
        db,
        module="posts",
        action="updated",
        user_id=current_user.id,
        entity_type="post",
        entity_id=post.id,
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(post)
    return post
