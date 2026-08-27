"""图片上传接口（多模态用）。

接收 multipart 文件，保存到 backend/uploads/images/YYYYMM/uuid.ext，
返回可访问的 URL。前端把这个 URL 放进 chat 请求的 image_url 字段。
"""
import os
import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.common import ApiResponse
from app.config import settings

router = APIRouter(prefix="/uploads", tags=["uploads"])

# 允许的图片扩展名（小写）
_ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
# 最大 8MB（DeepSeek / OpenAI Vision 都建议图片不超过这个量级）
_MAX_SIZE = 8 * 1024 * 1024


def _uploads_root() -> str:
    """uploads 目录绝对路径：backend/uploads/"""
    # backend/app/api/v1/uploads.py → 回到 backend/
    here = os.path.dirname(os.path.abspath(__file__))
    backend_root = os.path.abspath(os.path.join(here, "..", "..", ".."))
    return os.path.join(backend_root, "uploads")


def _build_url(path_rel_to_uploads: str) -> str:
    """把 backend/uploads/xxx/yyy.png 转成可访问 URL。"""
    # 后端在 main.py 里挂载了 /uploads 静态路由指向 backend/uploads
    base = (settings.UPLOAD_URL_BASE or "/uploads").rstrip("/")
    return f"{base}/{path_rel_to_uploads.replace(os.sep, '/')}"


@router.post("/image", response_model=ApiResponse)
def upload_image(
    file: UploadFile = File(...),
    current: User = Depends(get_current_user),
) -> JSONResponse:
    """上传一张图片，返回可访问 URL。"""
    # 1. 后缀校验
    orig_name = file.filename or ""
    ext = os.path.splitext(orig_name)[1].lower()
    if ext not in _ALLOWED_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的图片格式 {ext or '(无)'}，仅支持 {sorted(_ALLOWED_EXT)}",
        )

    # 2. 读内容 + 大小校验
    data = file.file.read()
    if len(data) > _MAX_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"图片过大 {len(data) // 1024}KB，单张不超过 {_MAX_SIZE // 1024 // 1024}MB",
        )

    # 3. 按 YYYYMM 分目录存放
    ym = datetime.now().strftime("%Y%m")
    save_dir = os.path.join(_uploads_root(), "images", ym)
    os.makedirs(save_dir, exist_ok=True)

    # 4. 用 uuid 避免重名
    new_name = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(save_dir, new_name)
    with open(save_path, "wb") as f:
        f.write(data)

    # 5. 返回可访问 URL
    rel = os.path.relpath(save_path, _uploads_root())
    url = _build_url(rel)
    return JSONResponse({"code": 0, "msg": "ok", "data": {"url": url, "filename": orig_name, "size": len(data)}})


@router.get("/image/list")
def list_my_images(current: User = Depends(get_current_user)) -> JSONResponse:
    """可选：列出当前用户最近上传的图片（暂返回空，前端暂未用到）。"""
    return JSONResponse({"code": 0, "msg": "ok", "data": []})
