# backend/modules/menu/utils/pagination_utils.py

"""
Pagination utilities for handling large datasets.
Supports both offset-based and cursor-based pagination.
"""

import base64
import json
from typing import TypeVar, Generic, List, Optional, Dict, Any, Tuple, Callable
from datetime import datetime
from sqlalchemy.orm import Query
from sqlalchemy import and_, or_, desc, asc
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CursorInfo(BaseModel):
    """Cursor information for pagination"""

    last_id: int
    last_value: Optional[Any] = None
    direction: str = "next"  # 'next' or 'prev'
    timestamp: datetime = None

    def encode(self) -> str:
        """Encode cursor to base64 string"""
        data = self.dict()
        # Convert datetime to string
        if data.get("timestamp"):
            data["timestamp"] = data["timestamp"].isoformat()
        json_str = json.dumps(data)
        return base64.b64encode(json_str.encode()).decode()

    @classmethod
    def decode(cls, cursor: str) -> "CursorInfo":
        """Decode cursor from base64 string"""
        try:
            json_str = base64.b64decode(cursor.encode()).decode()
            data = json.loads(json_str)
            # Convert string back to datetime
            if data.get("timestamp"):
                data["timestamp"] = datetime.fromisoformat(data["timestamp"])
            return cls(**data)
        except Exception as e:
            logger.error(f"Invalid cursor: {e}")
            raise ValueError("Invalid cursor format")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response model"""

    items: List[T]
    total: Optional[int] = None
    page_info: Dict[str, Any]

    class Config:
        arbitrary_types_allowed = True


class CursorPaginator:
    """
    Cursor-based pagination for large datasets.
    More efficient than offset pagination for large datasets.
    """

    def __init__(
        self,
        query: Query,
        order_by_field: str,
        unique_field: str = "id",
        page_size: int = 50,
        max_page_size: int = 100,
    ):
        """
        Initialize cursor paginator.

        Args:
            query: SQLAlchemy query object
            order_by_field: Field to order by (e.g., 'created_at')
            unique_field: Unique field for stable sorting (default: 'id')
            page_size: Default page size
            max_page_size: Maximum allowed page size
        """
        self.query = query
        self.order_by_field = order_by_field
        self.unique_field = unique_field
        self.page_size = min(page_size, max_page_size)
        self.max_page_size = max_page_size

    def paginate(
        self,
        cursor: Optional[str] = None,
        page_size: Optional[int] = None,
        include_total: bool = False,
    ) -> PaginatedResponse:
        """
        Get paginated results using cursor.

        Args:
            cursor: Encoded cursor string
            page_size: Number of items per page
            include_total: Whether to include total count (expensive)

        Returns:
            PaginatedResponse with items and pagination info
        """
        page_size = min(page_size or self.page_size, self.max_page_size)

        # Decode cursor if provided
        cursor_info = None
        if cursor:
            try:
                cursor_info = CursorInfo.decode(cursor)
            except ValueError:
                cursor_info = None

        # Build query with cursor filter
        if cursor_info:
            query = self._apply_cursor_filter(self.query, cursor_info)
        else:
            query = self.query

        # Apply ordering
        model = self.query.column_descriptions[0]["entity"]
        order_field = getattr(model, self.order_by_field)
        unique_field = getattr(model, self.unique_field)

        query = query.order_by(
            (
                desc(order_field)
                if cursor_info and cursor_info.direction == "prev"
                else asc(order_field)
            ),
            asc(unique_field),
        )

        # Fetch items + 1 to check if there's a next page
        items = query.limit(page_size + 1).all()

        # Check if there are more items
        has_next = len(items) > page_size
        if has_next:
            items = items[:-1]  # Remove the extra item

        # Generate cursors
        next_cursor = None
        prev_cursor = None

        if items:
            # Next cursor from last item
            if has_next:
                last_item = items[-1]
                next_cursor = CursorInfo(
                    last_id=getattr(last_item, self.unique_field),
                    last_value=getattr(last_item, self.order_by_field),
                    direction="next",
                    timestamp=datetime.utcnow(),
                ).encode()

            # Previous cursor from first item
            if cursor_info or self._has_previous_items(items[0]):
                first_item = items[0]
                prev_cursor = CursorInfo(
                    last_id=getattr(first_item, self.unique_field),
                    last_value=getattr(first_item, self.order_by_field),
                    direction="prev",
                    timestamp=datetime.utcnow(),
                ).encode()

        # Get total count if requested
        total = None
        if include_total:
            total = self.query.count()

        return PaginatedResponse(
            items=items,
            total=total,
            page_info={
                "has_next": has_next,
                "has_previous": bool(prev_cursor),
                "next_cursor": next_cursor,
                "prev_cursor": prev_cursor,
                "page_size": page_size,
                "cursor_field": self.order_by_field,
            },
        )

    def _apply_cursor_filter(self, query: Query, cursor_info: CursorInfo) -> Query:
        """Apply cursor filter to query"""
        model = query.column_descriptions[0]["entity"]
        order_field = getattr(model, self.order_by_field)
        unique_field = getattr(model, self.unique_field)

        if cursor_info.direction == "next":
            # For next page: where (order_field > last_value) OR
            # (order_field = last_value AND unique_field > last_id)
            return query.filter(
                or_(
                    order_field > cursor_info.last_value,
                    and_(
                        order_field == cursor_info.last_value,
                        unique_field > cursor_info.last_id,
                    ),
                )
            )
        else:
            # For previous page: where (order_field < last_value) OR
            # (order_field = last_value AND unique_field < last_id)
            return query.filter(
                or_(
                    order_field < cursor_info.last_value,
                    and_(
                        order_field == cursor_info.last_value,
                        unique_field < cursor_info.last_id,
                    ),
                )
            )

    def _has_previous_items(self, first_item: Any) -> bool:
        """Check if there are items before the first item"""
        model = self.query.column_descriptions[0]["entity"]
        order_field = getattr(model, self.order_by_field)
        unique_field = getattr(model, self.unique_field)

        first_value = getattr(first_item, self.order_by_field)
        first_id = getattr(first_item, self.unique_field)

        # Check if there's at least one item before
        exists = (
            self.query.filter(
                or_(
                    order_field < first_value,
                    and_(order_field == first_value, unique_field < first_id),
                )
            )
            .limit(1)
            .count()
            > 0
        )

        return exists


class HybridPaginator:
    """
    Hybrid paginator that supports both offset and cursor pagination.
    Automatically switches to cursor pagination for large offsets.
    """

    def __init__(
        self,
        query: Query,
        order_by_field: str = "id",
        offset_threshold: int = 1000,
        page_size: int = 50,
    ):
        """
        Initialize hybrid paginator.

        Args:
            query: SQLAlchemy query
            order_by_field: Field to order by
            offset_threshold: Offset at which to switch to cursor pagination
            page_size: Default page size
        """
        self.query = query
        self.order_by_field = order_by_field
        self.offset_threshold = offset_threshold
        self.page_size = page_size
        self.cursor_paginator = CursorPaginator(
            query, order_by_field, page_size=page_size
        )

    def paginate(
        self,
        page: Optional[int] = None,
        cursor: Optional[str] = None,
        page_size: Optional[int] = None,
    ) -> PaginatedResponse:
        """
        Paginate using either offset or cursor.

        Args:
            page: Page number for offset pagination
            cursor: Cursor for cursor pagination
            page_size: Items per page

        Returns:
            PaginatedResponse
        """
        page_size = page_size or self.page_size

        # Use cursor if provided
        if cursor:
            return self.cursor_paginator.paginate(cursor, page_size)

        # Calculate offset
        page = page or 1
        offset = (page - 1) * page_size

        # Switch to cursor pagination for large offsets
        if offset >= self.offset_threshold:
            logger.info(
                f"Switching to cursor pagination for offset {offset} "
                f"(threshold: {self.offset_threshold})"
            )
            # Create synthetic cursor for the offset
            # This requires fetching the item at the offset
            offset_item = self.query.offset(offset - 1).limit(1).first()
            if offset_item:
                cursor_info = CursorInfo(
                    last_id=getattr(offset_item, "id"),
                    last_value=getattr(offset_item, self.order_by_field),
                    direction="next",
                )
                return self.cursor_paginator.paginate(cursor_info.encode(), page_size)

        # Use offset pagination
        total = self.query.count()
        items = self.query.offset(offset).limit(page_size).all()

        total_pages = (total + page_size - 1) // page_size

        return PaginatedResponse(
            items=items,
            total=total,
            page_info={
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "total_items": total,
                "has_next": page < total_pages,
                "has_previous": page > 1,
                "offset": offset,
                "using_cursor": False,
            },
        )


def paginate_query(
    query: Query,
    page: int = 1,
    page_size: int = 50,
    max_page_size: int = 100,
    order_by: Optional[str] = None,
) -> Tuple[List[Any], Dict[str, Any]]:
    """
    Simple offset-based pagination helper.

    Args:
        query: SQLAlchemy query
        page: Page number (1-based)
        page_size: Items per page
        max_page_size: Maximum allowed page size
        order_by: Optional order by field

    Returns:
        Tuple of (items, pagination_info)
    """
    page = max(1, page)
    page_size = min(page_size, max_page_size)

    if order_by:
        model = query.column_descriptions[0]["entity"]
        order_field = getattr(model, order_by, None)
        if order_field:
            query = query.order_by(order_field)

    total = query.count()
    offset = (page - 1) * page_size
    items = query.offset(offset).limit(page_size).all()

    total_pages = (total + page_size - 1) // page_size

    pagination_info = {
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "total_items": total,
        "has_next": page < total_pages,
        "has_previous": page > 1,
        "offset": offset,
    }

    return items, pagination_info
