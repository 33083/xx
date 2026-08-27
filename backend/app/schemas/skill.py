"""技能模块 Schema。"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class SkillOut(BaseModel):
    """对外暴露的技能信息。"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    skill_key: str
    name: str
    description: Optional[str] = None
    category: str
    category_label: str = ""
    icon: str = "MagicStick"
    enabled: bool = True
    source: str = "builtin"  # builtin / langchain_community
    owner_id: Optional[int] = None
    updated_at: Optional[datetime] = None


class SkillToggleRequest(BaseModel):
    """启用/禁用技能请求。"""
    enabled: bool


# ---------- 市场相关 ----------

class MarketToolOut(BaseModel):
    """市场技能元信息（不区分是否已安装）。"""
    skill_key: str
    name: str
    description: str
    category: str
    category_label: str
    icon: str
    source: str  # langchain_community / langchain_experimental
    requirements: List[str] = []
    available: bool = False       # 依赖是否已装好
    installed: bool = False       # 当前用户是否已安装


class MarketInstallOut(BaseModel):
    """安装/卸载结果。"""
    skill_key: str
    installed: bool
    message: str = ""

