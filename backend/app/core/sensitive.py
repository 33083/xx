"""敏感词过滤：检测用户输入中的违规内容，避免系统被用于不良用途。"""
SENSITIVE_WORDS = [
    "赌博", "博彩", "时时彩", "六合彩", "开户返佣", "澳门赌场",
    "代开发票", "刷单兼职", "办假证", "裸聊", "约炮",
    "枪支", "冰毒", "大麻", "摇头丸", "毒品", "制毒",
]


def check_sensitive(text: str) -> str | None:
    """返回命中的第一个敏感词；无命中返回 None。"""
    if not text:
        return None
    for w in SENSITIVE_WORDS:
        if w in text:
            return w
    return None
