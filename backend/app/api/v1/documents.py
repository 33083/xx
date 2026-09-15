"""文档模块路由：上传 / 列表 / 删除 / 检索片段。"""
import mimetypes
import os
import re
import urllib.parse
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, status
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
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """上传文档：同步保存文件 + 建库记录，异步做文本提取/切块/向量化。

    通过 BackgroundTasks 调用 document_service.process_document_async，
    避免大文件解析阻塞上传响应。chunk_count 在异步处理完成后更新。
    """
    import shutil
    import uuid
    from datetime import datetime

    from sqlalchemy import select

    from app.core.vectorstore import user_collection_name
    from app.models.document import Document

    try:
        raw = file.filename or "unnamed"
        ext = os.path.splitext(raw)[1].lower()
        if ext not in document_service._ALLOWED_EXT:
            raise ValueError(f"不支持的文件类型：{ext or '无'}，支持 {sorted(document_service._ALLOWED_EXT)}")

        # 1. 保存文件
        storage = document_service._ensure_dirs()
        safe_name = f"{datetime.now():%Y%m%d}_{uuid.uuid4().hex[:8]}_{os.path.basename(raw)}"
        target = storage / f"u{current.id}" / safe_name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as fout:
            shutil.copyfileobj(file.file, fout)
        file_size = target.stat().st_size
        max_bytes = settings.DOC_MAX_MB * 1024 * 1024
        if file_size > max_bytes:
            target.unlink(missing_ok=True)
            raise ValueError(f"文件过大：{file_size // 1024 // 1024}MB，上限 {settings.DOC_MAX_MB}MB")

        # 2. 计算 MD5 去重
        digest = document_service._md5_of(target)
        existing = db.scalar(
            select(Document).where(Document.owner_id == current.id, Document.md5 == digest)
        )
        if existing is not None:
            target.unlink(missing_ok=True)
            raise ValueError(f"相同内容的文件已存在：{existing.title}")

        # 3. 创建 Document 记录（chunk_count 先设为 0，异步处理完成后更新）
        doc = Document(
            owner_id=current.id,
            title=raw,
            file_type=document_service._file_type(ext),
            file_path=str(target),
            file_size=file_size,
            md5=digest,
            category=document_service._category_of(raw, category),
            chroma_collection=user_collection_name(current.id),
            chunk_count=0,
            description=description,
        )
        db.add(doc)
        db.flush()

        # 4. 提交到数据库
        db.commit()
        db.refresh(doc)

        # 5. 用 BackgroundTasks 添加 process_document_async 任务
        background_tasks.add_task(
            document_service.process_document_async,
            doc.id, current.id, str(target), ext,
        )

        # 6. 立即返回
        return ApiResponse(data=DocumentUploaded(
            id=doc.id, title=doc.title, chunk_count=doc.chunk_count, category=doc.category,
        ))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


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
