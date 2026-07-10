from typing import Annotated

from fastapi import APIRouter, Query, Request
from sqlalchemy import func, or_, select

from app.api.deps import CurrentUser, SessionDep, TexnologUser
from app.core.config import settings
from app.core.exceptions import DuplicateValueException, NotFoundException
from app.crud import crud_materials, log_action
from app.models import Material
from app.models.enums import MaterialType
from app.schemas.common import Message, Paginated
from app.schemas.materials import MaterialCreate, MaterialRead, MaterialUpdate

router = APIRouter(prefix="/materials", tags=["materials"])


@router.get("/", response_model=Paginated[MaterialRead], operation_id="read_materials")
async def read_materials(
    db: SessionDep,
    _: CurrentUser,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=settings.MAX_PAGE_SIZE)] = settings.DEFAULT_PAGE_SIZE,
    search: str | None = None,
    type: MaterialType | None = None,
) -> Paginated[MaterialRead]:
    query = select(Material).where(Material.is_deleted == False)  # noqa: E712
    if type is not None:
        query = query.where(Material.type == type)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(or_(Material.name.ilike(pattern), Material.code.ilike(pattern)))

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = (await db.execute(query.order_by(Material.name).offset(skip).limit(limit))).scalars().all()
    return Paginated(data=[MaterialRead.model_validate(m) for m in rows], count=total)


@router.post("/", response_model=MaterialRead, status_code=201, operation_id="create_material")
async def create_material(
    db: SessionDep, current_user: TexnologUser, body: MaterialCreate, request: Request
) -> Material:
    if await crud_materials.exists(db, name=body.name, type=body.type):
        raise DuplicateValueException("Bu nomdagi material allaqachon mavjud.")
    material = Material(**body.model_dump())
    db.add(material)
    await db.flush()
    log_action(
        db,
        module="materials",
        action="created",
        user_id=current_user.id,
        entity_type="material",
        entity_id=material.id,
        message=f"Material qo'shildi: {material.name}",
        ip=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(material)
    return material


@router.patch("/{material_id}", response_model=MaterialRead, operation_id="update_material")
async def update_material(
    db: SessionDep, current_user: TexnologUser, material_id: int, body: MaterialUpdate, request: Request
) -> Material:
    material = await crud_materials.get(db, id=material_id)
    if material is None:
        raise NotFoundException("Material topilmadi.")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(material, field, value)
    log_action(
        db,
        module="materials",
        action="updated",
        user_id=current_user.id,
        entity_type="material",
        entity_id=material.id,
        ip=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(material)
    return material


@router.delete("/{material_id}", response_model=Message, operation_id="delete_material")
async def delete_material(db: SessionDep, current_user: TexnologUser, material_id: int, request: Request) -> Message:
    material = await crud_materials.get(db, id=material_id)
    if material is None:
        raise NotFoundException("Material topilmadi.")
    log_action(
        db,
        module="materials",
        action="deleted",
        user_id=current_user.id,
        entity_type="material",
        entity_id=material.id,
        message=f"Material o'chirildi: {material.name}",
        ip=request.client.host if request.client else None,
    )
    await crud_materials.delete(db, id=material_id)
    return Message(message="Material o'chirildi.")
