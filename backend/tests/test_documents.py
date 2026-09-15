"""文档服务冒烟测试。"""
from app.services.document_service import process_document_async


def test_process_document_async_not_exist():
    """处理不存在的文档 ID 应安全返回。"""
    # 不应抛异常
    process_document_async(doc_id=99999, owner_id=1, file_path="/tmp/nonexist.txt", ext=".txt")
