from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile, status

from ..admin_auth import (
    ADMIN_SESSION_COOKIE,
    ADMIN_USERNAME,
    authenticate_admin,
    clear_admin_session_cookie,
    require_admin,
    set_admin_session_cookie,
    validate_admin_session_token,
)
from ..repositories.admin_content import (
    create_series,
    delete_series,
    get_series_detail,
    list_series,
    restore_series,
    upload_episode_danmaku,
    upload_episode_video,
    upload_series_cover,
)
from ..repositories.admin_dashboard import get_admin_dashboard
from ..schemas import (
    AdminAuthResponse,
    AdminDashboardResponse,
    AdminDanmakuUploadResponse,
    AdminEpisodeUploadResponse,
    AdminLoginRequest,
    AdminSeriesCreate,
    AdminSeriesDeleteResponse,
    AdminSeriesDetail,
    AdminSeriesListResponse,
    AdminSeriesResponse,
    AdminSeriesRestoreResponse,
    AdminUploadResponse,
)

router = APIRouter()


@router.post("/admin/auth/login", response_model=AdminAuthResponse)
def login_admin(payload: AdminLoginRequest, response: Response) -> AdminAuthResponse:
    if not authenticate_admin(payload.username, payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin credentials")
    set_admin_session_cookie(response)
    return AdminAuthResponse(authenticated=True, username=ADMIN_USERNAME)


@router.get("/admin/auth/me", response_model=AdminAuthResponse)
def get_admin_auth_state(request: Request) -> AdminAuthResponse:
    authenticated = validate_admin_session_token(request.cookies.get(ADMIN_SESSION_COOKIE))
    return AdminAuthResponse(authenticated=authenticated, username=ADMIN_USERNAME if authenticated else None)


@router.post("/admin/auth/logout", response_model=AdminAuthResponse)
def logout_admin(response: Response) -> AdminAuthResponse:
    clear_admin_session_cookie(response)
    return AdminAuthResponse(authenticated=False, username=None)


@router.get("/admin/dashboard", response_model=AdminDashboardResponse)
def retrieve_admin_dashboard(_: None = Depends(require_admin)) -> AdminDashboardResponse:
    return AdminDashboardResponse(**get_admin_dashboard())


@router.get("/admin/series", response_model=AdminSeriesListResponse)
def list_admin_series(_: None = Depends(require_admin)) -> AdminSeriesListResponse:
    return AdminSeriesListResponse(series=list_series())


@router.get("/admin/series/{series_id}", response_model=AdminSeriesDetail)
def retrieve_admin_series(series_id: str, _: None = Depends(require_admin)) -> AdminSeriesDetail:
    return AdminSeriesDetail(**get_series_detail(series_id))


@router.delete("/admin/series/{series_id}", response_model=AdminSeriesDeleteResponse)
def delete_admin_series(series_id: str, _: None = Depends(require_admin)) -> AdminSeriesDeleteResponse:
    return AdminSeriesDeleteResponse(**delete_series(series_id))


@router.post("/admin/series/{series_id}/restore", response_model=AdminSeriesRestoreResponse)
def restore_admin_series(series_id: str, _: None = Depends(require_admin)) -> AdminSeriesRestoreResponse:
    return AdminSeriesRestoreResponse(**restore_series(series_id))


@router.post("/admin/series", response_model=AdminSeriesResponse)
async def create_admin_series(payload: AdminSeriesCreate, _: None = Depends(require_admin)) -> AdminSeriesResponse:
    return AdminSeriesResponse(**await create_series(payload.series_id, payload.series_name))


@router.post("/admin/series/{series_id}/cover", response_model=AdminUploadResponse)
async def upload_admin_series_cover(
    series_id: str,
    file: UploadFile = File(...),
    _: None = Depends(require_admin),
) -> AdminUploadResponse:
    return AdminUploadResponse(**await upload_series_cover(series_id, file))


@router.post("/admin/series/{series_id}/episodes", response_model=AdminEpisodeUploadResponse)
async def upload_admin_episode(
    series_id: str,
    series_name: str = Form(...),
    episode_no: int = Form(...),
    title: str = Form(...),
    video: UploadFile = File(...),
    _: None = Depends(require_admin),
) -> AdminEpisodeUploadResponse:
    return AdminEpisodeUploadResponse(
        **await upload_episode_video(
            series_id=series_id,
            series_name=series_name,
            episode_no=episode_no,
            title=title,
            video=video,
        )
    )


@router.post("/admin/series/{series_id}/episodes/{episode_label}/danmaku", response_model=AdminDanmakuUploadResponse)
async def upload_admin_episode_danmaku(
    series_id: str,
    episode_label: str,
    file: UploadFile = File(...),
    _: None = Depends(require_admin),
) -> AdminDanmakuUploadResponse:
    return AdminDanmakuUploadResponse(**await upload_episode_danmaku(series_id, episode_label, file))
