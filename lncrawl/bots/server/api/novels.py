from typing import List

from fastapi import APIRouter, Depends, Path, Query, Security
from fastapi.responses import FileResponse

from ..context import ServerContext
from ..models.novel import Artifact, Novel, NovelChapterContent, NovelVolume
from ..models.pagination import Paginated
from ..security import ensure_user
from ..models.user import User

# The root router
router = APIRouter()


@router.get("s", summary='Returns a list of novels',
            dependencies=[Security(ensure_user)], )
def list_novels(
    ctx: ServerContext = Depends(),
    search: str = Query(default=''),
    offset: int = Query(default=0),
    limit: int = Query(default=20, le=100),
    with_orphans: bool = Query(default=False),
) -> Paginated[Novel]:
    return ctx.novels.list(
        limit=limit,
        offset=offset,
        search=search.strip(),
        with_orphans=with_orphans,
    )


@router.get("/{novel_id}", summary='Returns a novel')
def get_novel(
    novel_id: str = Path(),
    ctx: ServerContext = Depends(),
) -> Novel:
    return ctx.novels.get(novel_id)


@router.get("/{novel_id}/artifacts", summary='Returns cached artifacts',
            dependencies=[Security(ensure_user)])
def get_novel_artifacts(
    novel_id: str = Path(),
    ctx: ServerContext = Depends(),
) -> List[Artifact]:
    return ctx.novels.get_artifacts(novel_id)


@router.get("/{novel_id}/cover", summary='Returns a novel cover')
async def get_novel_cover(
    novel_id: str = Path(),
    ctx: ServerContext = Depends(),
) -> FileResponse:
    return await ctx.metadata.get_novel_cover(novel_id)


@router.get("/{novel_id}/toc", summary='Gets table of contents')
async def get_novel_toc(
    novel_id: str = Path(),
    ctx: ServerContext = Depends(),
) -> List[NovelVolume]:
    return ctx.metadata.get_novel_toc(novel_id)


@router.get("/{novel_id}/chapter/{hash}", summary='Gets chapter content')
async def get_chapter_json(
    novel_id: str = Path(),
    hash: str = Path(),
    ctx: ServerContext = Depends(),
) -> NovelChapterContent:
    return ctx.metadata.get_novel_chapter_content(novel_id, hash)


@router.delete("/{novel_id}", summary='Deletes a novel', dependencies=[Security(ensure_user)])
def delete_novel(
    novel_id: str = Path(),
    ctx: ServerContext = Depends(),
    user: User = Security(ensure_user)
) -> bool:
    return ctx.novels.delete(novel_id, user)


@router.put("/{novel_id}/schedule", summary='Updates novel schedule', dependencies=[Security(ensure_user)])
def update_schedule(
    schedule_config: dict,
    novel_id: str = Path(),
    ctx: ServerContext = Depends(),
) -> Novel:
    return ctx.novels.update_schedule(novel_id, schedule_config)

