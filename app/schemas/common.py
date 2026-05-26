"""공통 스키마 - 여러 도메인이 공유하는 형태"""
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """페이지네이션 응답 envelope - 고볼륨 admin 목록 엔드포인트 공통.

    프론트는 `res.items`를 순회하고 `res.total`로 전체 건수, `res.page`/`res.page_size`로
    현재 페이지 정보 표시. 카운트·차트 등 전체 집계가 필요하면 `/admin/dashboard/summary`를 쓸 것.
    """
    items: list[T]
    total: int
    page: int
    page_size: int
