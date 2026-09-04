"""文档模块路由：上传 / 列表 / 删除 / 检索片段。"""
import mimetypes
import os
import re
import urllib.parse
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import settings
from app.database import get_db
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.document import (
    DocDeleteOut,
    DocumentListOut,
    DocumentOut,
    DocumentPreviewOut,
    DocumentUpdate,
    DocumentUploaded,
    RagSearchOut,
)
from app.services import document_service, rag_service

router = APIRouter(prefix="/documents", tags=["documents"])


def _build_storage_path(rel_or_abs: str) -> Path:
    """DB 中相对路径转绝对路径（避免 uvicorn cwd 不同导致文件找不到）。"""
    p = Path(rel_or_abs)
    if p.is_absolute():
        return p
    base = Path(settings.DOC_STORAGE_DIR)
    if not base.is_absolute():
        backend_root = Path(__file__).resolve().parents[3]
        base = backend_root / settings.DOC_STORAGE_DIR
    candidate = base / rel_or_abs
    if candidate.exists():
        return candidate
    if p.exists():
        return p.resolve()
    return candidate  # 上层用 Path.exists() 判 404


def _rfc5987_cd(filename: str, *, inline: bool = True) -> str:
    """Content-Disposition: ASCII fallback filename + RFC 5987 filename*=UTF-8''.

    原写法 filename="中文.pdf" 让 Starlette 用 latin-1 编码 header 抛：
      UnicodeEncodeError: 'latin-1' codec can't encode characters → 500 Internal Server Error
    修复：filename= 里非 ASCII 换成下划线作为旧浏览器 fallback，
          实际中文字符文件名走 filename*=UTF-8'' 百分号编码（RFC 5987，所有现代浏览器支持）。
    """
    safe_ascii = re.sub(r"[^\x20-\x7E]", "_", filename) or "download"
    encoded = urllib.parse.quote(filename, safe="")
    kind = "inline" if inline else "attachment"
    return f'{kind}; filename="{safe_ascii}"; filename*=UTF-8\'\'{encoded}'


@router.post("/upload", response_model=ApiResponse[DocumentUploaded])
async def upload_document(
    file: UploadFile = File(..., description="PDF/TXT/MD/DOCX/PPTX..."),
    category: str | None = Form(None, description="material/resume/interview，留空按文件名猜"),
    description: str | None = Form(None, description="备注"),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = document_service.save_upload(
            current.id, file, db, category=category, description=description,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    return ApiResponse(data=result)


@router.get("", response_model=ApiResponse[DocumentListOut])
def list_my_docs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: str | None = Query(None, description="material/resume/interview"),
    keyword: str | None = Query(None, max_length=100, description="按标题/备注模糊搜索"),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items, total = document_service.list_my_documents(
        current.id, db, category=category, keyword=keyword, page=page, page_size=page_size,
    )
    return ApiResponse(
        data=DocumentListOut(items=items, total=total, page=page, page_size=page_size),
    )


@router.delete("/{doc_id}", response_model=ApiResponse[DocDeleteOut])
def delete_my_doc(
    doc_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ok = document_service.delete_document(current.id, doc_id, db)
    if not ok:
        raise HTTPException(status_code=404, detail="文档不存在或无权删除")
    return ApiResponse(data=DocDeleteOut(deleted=True))


@router.get("/search", response_model=ApiResponse[RagSearchOut])
def rag_search_test(
    q: str,
    top_k: int = 4,
    current: User = Depends(get_current_user),
):
    """RAG 检索接口（调试/前端预览用，真正的 RAG 在 /chat 里走链）。"""
    if not q.strip():
        raise HTTPException(status_code=400, detail="q 不能为空")
    out = rag_service.rag_search(current.id, q, top_k=top_k)
    return ApiResponse(data=out)


@router.patch("/{doc_id}", response_model=ApiResponse[DocumentOut])
def update_my_doc(
    doc_id: int,
    payload: DocumentUpdate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.title is None and payload.description is None:
        raise HTTPException(status_code=400, detail="至少提供 title 或 description 之一")
    doc = document_service.update_document(
        current.id, doc_id, db, title=payload.title, description=payload.description,
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="文档不存在或无权编辑")
    return ApiResponse(data=doc)


@router.get("/{doc_id}/preview", response_model=ApiResponse[DocumentPreviewOut])
def preview_my_doc(
    doc_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = document_service.get_document(current.id, doc_id, db)
    if doc is None:
        raise HTTPException(status_code=404, detail="文档不存在或无权访问")
    out = DocumentPreviewOut(
        doc_id=doc.id, title=doc.title, file_type=doc.file_type, category=doc.category,
    )
    if doc.file_type == "pdf":
        out.preview_url = f"{settings.API_V1_PREFIX}/documents/{doc.id}/file"
    else:
        try:
            out.text = document_service.preview_text(doc.file_path)
        except Exception as e:
            out.text = f"[预览失败] {e}"
    return ApiResponse(data=out)


@router.get("/{doc_id}/file")
def download_my_doc_file(
    doc_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = document_service.get_document(current.id, doc_id, db)
    if doc is None:
        raise HTTPException(status_code=404, detail="文档不存在或无权访问")
    path = _build_storage_path(doc.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="文件已丢失")
    media_map = {
        "pdf": "application/pdf",
        "txt": "text/plain; charset=utf-8",
        "md": "text/markdown; charset=utf-8",
        "markdown": "text/markdown; charset=utf-8",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "doc": "application/msword",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }
    media_type = media_map.get(doc.file_type) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    filename = os.path.basename(doc.file_path)
    # 不要手动写 resp.headers["Content-Disposition"] = 'inline; filename="中文.pdf"'
    # Starlette 给 header 赋值时用 latin-1 编码字符串，中文字符会抛：
    #   UnicodeEncodeError: "latin-1" codec can't encode characters → 500 Internal Server Error
    # 直接用 Starlette 自带的 content_disposition_type + filename 参数，
    # Starlette 内部会自动生成 RFC 5987 的 filename*=utf-8'<百分号编码> 格式，完全没有中文问题。
    return FileResponse(
        path=path,
        media_type=media_type,
        filename=filename,
        content_disposition_type="inline",
    )
