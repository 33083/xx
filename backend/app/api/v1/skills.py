"""技能管理 REST 路由。

提供：
- GET    /api/v1/skills                          列出当前用户的所有技能（含启用状态）
- PUT    /api/v1/skills/{key}                    更新技能状态（启用/禁用）
- GET    /api/v1/skills/market                  列出技能市场所有可下载技能
- POST   /api/v1/skills/market/install/{key}     从市场安装一个技能
- DELETE /api/v1/skills/market/uninstall/{key}  卸载已安装的市场技能
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.database import get_db as _get_db  # noqa: F401  保持兼容
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.skill import (
    MarketInstallOut,
    MarketToolOut,
    SkillOut,
    SkillToggleRequest,
)
from app.services import skill_service

router = APIRouter(prefix="/skills", tags=["skills"])


# ---------- 元信息查找辅助 ----------

def _meta_for(skill_key: str) -> dict:
    """合并 builtin + market 的元信息。"""
    for m in skill_service.list_builtin_skills():
        if m["skill_key"] == skill_key:
            return m
    for m in skill_service.list_market_tools():
        if m["skill_key"] == skill_key:
            return m
    return {}


def _to_out(row) -> SkillOut:
    """把 Skill ORM 行 + 内置元信息组装成 SkillOut。"""
    meta = _meta_for(row.skill_key)
    return SkillOut(
        id=row.id,
        skill_key=row.skill_key,
        name=row.name,
        description=row.description,
        category=row.category,
        category_label=meta.get("category_label", ""),
        icon=meta.get("icon", "MagicStick"),
        enabled=row.enabled,
        source=meta.get("source", "builtin"),
        owner_id=row.owner_id,
        updated_at=row.updated_at,
    )


# ---------- 我的技能 ----------

@router.get("", response_model=ApiResponse[list[SkillOut]])
def list_skills(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = skill_service.get_user_skills(current, db)
    return ApiResponse(data=[_to_out(r) for r in rows])


@router.put("/{skill_key}", response_model=ApiResponse[SkillOut])
def update_skill(
    skill_key: str,
    payload: SkillToggleRequest,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = skill_service.set_skill_enabled(current, skill_key, payload.enabled, db)
    return ApiResponse(data=_to_out(row))


# ---------- 技能市场 ----------

@router.get("/market", response_model=ApiResponse[list[MarketToolOut]])
def list_market(
    q: str = Query(default="", description="按 name/description 模糊搜索"),
    category: str = Query(default="", description="按 category 过滤"),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """列出技能市场所有可下载技能。

    - 支持 ?q=搜索 关键词模糊匹配 name/description
    - 支持 ?category=search 只看某个分类
    - 每项返回 installed 字段表示当前用户是否已安装
    """
    all_tools = skill_service.list_market_tools()
    # 已安装的 keys 集合
    installed_rows = skill_service.get_user_skills(current, db)
    installed_keys = {r.skill_key for r in installed_rows}

    kw = q.strip().lower()
    cat = category.strip().lower()

    out: list[MarketToolOut] = []
    for t in all_tools:
        # 过滤分类
        if cat and t["category"] != cat:
            continue
        # 过滤关键词
        if kw:
            blob = (t["name"] + " " + t["description"] + " " + t["category_label"]).lower()
            if kw not in blob:
                continue
        out.append(MarketToolOut(
            skill_key=t["skill_key"],
            name=t["name"],
            description=t["description"],
            category=t["category"],
            category_label=t["category_label"],
            icon=t["icon"],
            source=t["source"],
            requirements=t.get("requirements", []),
            available=t["available"],
            installed=t["skill_key"] in installed_keys,
        ))
    return ApiResponse(data=out)


@router.post("/market/install/{skill_key}", response_model=ApiResponse[MarketInstallOut])
def install_market_skill(
    skill_key: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """从市场安装一个技能（同步启用）。"""
    row = skill_service.install_market_tool(current, skill_key, db)
    return ApiResponse(data=MarketInstallOut(
        skill_key=skill_key,
        installed=True,
        message=f"已安装并启用：{row.name}",
    ))


@router.delete("/market/uninstall/{skill_key}", response_model=ApiResponse[MarketInstallOut])
def uninstall_market_skill(
    skill_key: str,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """卸载已安装的市场技能。"""
    ok = skill_service.uninstall_market_tool(current, skill_key, db)
    return ApiResponse(data=MarketInstallOut(
        skill_key=skill_key,
        installed=False,
        message="已卸载" if ok else "未安装，无需卸载",
    ))
