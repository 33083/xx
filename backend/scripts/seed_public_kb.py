# -*- coding: utf-8 -*-
"""内置公共知识库种子脚本：克隆开源仓库 → 解析 markdown → 分块 → 索引到共享向量库。

用法（在 backend 目录、venv 环境）：
    python scripts/seed_public_kb.py
说明：
    - 共享集合 shared_interview_knowledge 会先清空再重建（幂等，可反复执行）。
    - 元数据与用户文档保持一致：{doc_id, doc_title, category, chunk_index}。
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

# 保证以 backend 为工作目录时能导入 app 包
BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.document_service import _chunk_text  # noqa: E402
from app.core.vectorstore import get_shared_vectorstore  # noqa: E402

# (github_repo, 优先分支, 分类, 显示前缀)
SOURCES = [
    ("0voice/Campus_recruitment_interview_questions", "main", "interview", "校招面试题"),
    ("Zchary1106/agent-interview-hub", "main", "interview", "AI面试"),
    ("CyC2018/CS-Notes", "master", "interview", "CS-Notes"),
    ("resumejob/awesome-resume", "master", "resume", "简历范例"),
    ("geekcompany/ResumeSample", "master", "resume", "简历模板"),
    ("dyweb/awesome-resume-for-chinese", "master", "resume", "中文简历"),
    ("jackfrued/Python-100-Days", "master", "material", "Python学习"),
]

# 上限控制（避免索引时间过长）
MAX_TOTAL_CHUNKS = 3000
MAX_PER_REPO_CHUNKS = 800
MIN_FILE_CHARS = 120


def _clone(repo: str, branches: list[str], dest: Path) -> bool:
    for branch in branches:
        url = f"https://github.com/{repo}.git"
        cmd = ["git", "clone", "--depth", "1", "--single-branch", "--branch", branch, url, str(dest)]
        print(f"  [clone] {repo} @ {branch}")
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0:
            return True
        print(f"    branch {branch} 失败：{r.stderr.strip()[-200:]}")
    return False


def _download_zip(repo: str, branches: list[str], dest: Path) -> bool:
    for branch in branches:
        url = f"https://codeload.github.com/{repo}/zip/refs/heads/{branch}"
        print(f"  [zip] {repo} @ {branch}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
            if not data.startswith(b"PK"):
                print("    非 zip 响应，跳过")
                continue
            tmp = Path(tempfile.gettempdir()) / (repo.replace("/", "_") + ".zip")
            tmp.write_bytes(data)
            with zipfile.ZipFile(tmp) as zf:
                zf.extractall(dest)
            tmp.unlink(missing_ok=True)
            return True
        except Exception as e:
            print(f"    失败：{e}")
    return False


def _iter_md_files(root: Path):
    for p in sorted(root.rglob("*.md")):
        if ".git" in p.parts:
            continue
        yield p


def _read_text(p: Path) -> str:
    raw = p.read_bytes()
    # 二进制/含 NUL 的文件跳过
    if b"\x00" in raw[:4096]:
        return ""
    for enc in ("utf-8", "utf-8-sig", "gbk"):
        try:
            return raw.decode(enc, errors="ignore")
        except Exception:
            continue
    return ""


def main() -> int:
    vs = get_shared_vectorstore()
    col = vs._collection  # noqa: SLF001

    # 1) 清空共享集合，保证幂等
    try:
        existing = col.count()
        if existing:
            ids = col.get(include=[], limit=existing)["ids"]
            col.delete(ids=ids)
            print(f"[reset] 已清空共享集合旧数据 {existing} 条")
    except Exception as e:
        print(f"[warn] 清空失败（可能本来为空）：{e}")

    total_chunks = 0
    doc_counter = 0
    batch: list[tuple[str, dict, str]] = []

    with tempfile.TemporaryDirectory(prefix="kb_seed_") as tmpdir:
        tmp = Path(tmpdir)
        for repo, branch, category, prefix in SOURCES:
            dest = tmp / repo.replace("/", "_")
            # github.com 主站经常被墙，优先走 codeload 下载 zip，clone 仅兜底
            ok = _download_zip(repo, [branch, "master", "main"], dest)
            if not ok:
                ok = _clone(repo, [branch, "master", "main"], dest)
            if not ok:
                print(f"  [SKIP] {repo} 克隆/下载失败")
                continue

            # 解压 zip 后会多一层目录，定位仓库根
            roots = [dest]
            subdirs = [d for d in dest.iterdir() if d.is_dir() and not d.name.startswith(".")]
            if len(subdirs) == 1 and not any(dest.rglob("*.md")):
                roots = [subdirs[0]]

            repo_chunks = 0
            repo_docs = 0
            for fp in _iter_md_files(dest):
                text = _read_text(fp)
                if len(text) < MIN_FILE_CHARS:
                    continue
                chunks = _chunk_text(text)
                if not chunks:
                    continue
                rel = fp.relative_to(dest).as_posix()
                title = f"{prefix}｜{rel}"
                doc_counter += 1
                repo_docs += 1
                for i, c in enumerate(chunks):
                    batch.append((
                        c,
                        {"doc_id": doc_counter, "doc_title": title, "category": category, "chunk_index": i},
                        f"s{doc_counter}_c{i}",
                    ))
                    repo_chunks += 1
                    total_chunks += 1
                    if total_chunks >= MAX_TOTAL_CHUNKS or repo_chunks >= MAX_PER_REPO_CHUNKS:
                        break
                if total_chunks >= MAX_TOTAL_CHUNKS:
                    break
            print(f"  [OK] {repo} → {category}：{repo_docs} 篇 / {repo_chunks} 块")
            if total_chunks >= MAX_TOTAL_CHUNKS:
                print("  [limit] 达到总块数上限，停止拉取更多仓库")
                break

    # 2) 分批写入向量库
    print(f"[index] 开始写入 {len(batch)} 个分块到共享向量库 ...")
    for start in range(0, len(batch), 200):
        slice_ = batch[start:start + 200]
        vs.add_texts(
            texts=[t for t, _, _ in slice_],
            metadatas=[m for _, m, _ in slice_],
            ids=[i for _, _, i in slice_],
        )
        print(f"  [index] 已写入 {min(start + 200, len(batch))}/{len(batch)}")
    final_count = col.count()
    print(f"\n[完成] 共享库现有 {final_count} 个分块")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
