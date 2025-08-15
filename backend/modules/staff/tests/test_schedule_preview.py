# backend/modules/staff/tests/test_schedule_preview.py

import pytest
from datetime import date, datetime, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
import json

from core.database import get_db
from modules.staff.models import Staff, StaffRole, Schedule
from modules.staff.services.schedule_cache_service import schedule_cache_service


@pytest.mark.asyncio
class TestSchedulePreview:
    """Integration tests for schedule preview endpoints"""

    async def setup_test_data(self, db: AsyncSession, restaurant_id: int):
        """Create test staff and schedules"""
        # Create roles
        roles = []
        for i, role_name in enumerate(["Server", "Cook", "Manager"]):
            role = StaffRole(
                restaurant_id=restaurant_id,
                name=role_name,
                description=f"{role_name} role",
                permissions=[],
            )
            db.add(role)
            roles.append(role)

        await db.flush()

        # Create staff members
        staff_members = []
        for i in range(15):  # Create 15 staff members
            staff = Staff(
                restaurant_id=restaurant_id,
                name=f"Staff {i+1}",
                email=f"staff{i+1}@test.com",
                phone=f"+1234567{i:04d}",
                role_id=roles[i % 3].id,
                is_active=True,
            )
            db.add(staff)
            staff_members.append(staff)

        await db.flush()

        # Create schedules for next 7 days
        schedules = []
        start_date = date.today()
        for day in range(7):
            current_date = start_date + timedelta(days=day)

            # Morning shift (8 staff)
            for i in range(8):
                schedule = Schedule(
                    restaurant_id=restaurant_id,
                    staff_id=staff_members[i].id,
                    date=current_date,
                    start_time="08:00",
                    end_time="16:00",
                    is_published=False,
                )
                db.add(schedule)
                schedules.append(schedule)

            # Evening shift (7 staff)
            for i in range(8, 15):
                schedule = Schedule(
                    restaurant_id=restaurant_id,
                    staff_id=staff_members[i].id,
                    date=current_date,
                    start_time="16:00",
                    end_time="23:00",
                    is_published=False,
                )
                db.add(schedule)
                schedules.append(schedule)

        await db.commit()

        return {"roles": roles, "staff": staff_members, "schedules": schedules}

    @pytest.mark.asyncio
    async def test_preview_basic(
        self, async_client: AsyncClient, test_db: AsyncSession, test_user
    ):
        """Test basic preview functionality"""
        # Setup test data
        test_data = await self.setup_test_data(test_db, test_user.restaurant_id)

        # Get preview for next 3 days
        start_date = date.today()
        end_date = start_date + timedelta(days=2)

        response = await async_client.get(
            "/api/v1/schedule/preview",
            params={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            headers={"Authorization": f"Bearer {test_user.token}"},
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "date_range" in data
        assert data["date_range"]["start"] == start_date.isoformat()
        assert data["date_range"]["end"] == end_date.isoformat()

        assert "total_shifts" in data
        assert data["total_shifts"] == 45  # 15 staff * 3 days

        assert "by_date" in data
        assert len(data["by_date"]) == 3

        assert "by_staff" in data
        assert len(data["by_staff"]) == 15

        assert "summary" in data
        assert data["summary"]["total_hours"] > 0
        assert data["summary"]["coverage_gaps"] == []

    @pytest.mark.asyncio
    async def test_preview_with_filters(
        self, async_client: AsyncClient, test_db: AsyncSession, test_user
    ):
        """Test preview with department/role filters"""
        test_data = await self.setup_test_data(test_db, test_user.restaurant_id)

        # Filter by role (Servers only)
        server_role = test_data["roles"][0]

        response = await async_client.get(
            "/api/v1/schedule/preview",
            params={
                "start_date": date.today().isoformat(),
                "end_date": date.today().isoformat(),
                "role_id": server_role.id,
            },
            headers={"Authorization": f"Bearer {test_user.token}"},
        )

        assert response.status_code == 200
        data = response.json()

        # Should only include servers (5 staff members)
        assert len(data["by_staff"]) == 5
        assert data["total_shifts"] == 5

    @pytest.mark.asyncio
    async def test_preview_caching(
        self, async_client: AsyncClient, test_db: AsyncSession, test_user
    ):
        """Test that preview results are cached"""
        await self.setup_test_data(test_db, test_user.restaurant_id)

        params = {
            "start_date": date.today().isoformat(),
            "end_date": date.today().isoformat(),
        }
        headers = {"Authorization": f"Bearer {test_user.token}"}

        # First request - should generate and cache
        response1 = await async_client.get(
            "/api/v1/schedule/preview", params=params, headers=headers
        )
        assert response1.status_code == 200
        data1 = response1.json()

        # Verify cache was populated
        cached = await schedule_cache_service.get_preview_cache(
            test_user.restaurant_id,
            datetime.combine(date.today(), datetime.min.time()),
            datetime.combine(date.today(), datetime.max.time()),
            {},
        )
        assert cached is not None
        assert "_cached_at" in cached

        # Second request - should use cache
        response2 = await async_client.get(
            "/api/v1/schedule/preview", params=params, headers=headers
        )
        assert response2.status_code == 200
        data2 = response2.json()

        # Data should be identical (except cache metadata)
        assert data1["total_shifts"] == data2["total_shifts"]
        assert data1["by_date"] == data2["by_date"]

    @pytest.mark.asyncio
    async def test_preview_cache_invalidation(
        self, async_client: AsyncClient, test_db: AsyncSession, test_user
    ):
        """Test cache invalidation on schedule changes"""
        test_data = await self.setup_test_data(test_db, test_user.restaurant_id)

        # Get initial preview (populates cache)
        params = {
            "start_date": date.today().isoformat(),
            "end_date": date.today().isoformat(),
        }
        headers = {"Authorization": f"Bearer {test_user.token}"}

        response1 = await async_client.get(
            "/api/v1/schedule/preview", params=params, headers=headers
        )
        initial_shifts = response1.json()["total_shifts"]

        # Create a new shift
        create_data = {
            "staff_id": test_data["staff"][0].id,
            "date": date.today().isoformat(),
            "start_time": "12:00",
            "end_time": "20:00",
        }

        await async_client.post(
            "/api/v1/schedule/shifts", json=create_data, headers=headers
        )

        # Get preview again - should have one more shift
        response2 = await async_client.get(
            "/api/v1/schedule/preview", params=params, headers=headers
        )
        new_shifts = response2.json()["total_shifts"]

        assert new_shifts == initial_shifts + 1

    @pytest.mark.asyncio
    async def test_paginated_preview(
        self, async_client: AsyncClient, test_db: AsyncSession, test_user
    ):
        """Test paginated preview for large staff lists"""
        # Create 60 staff members
        for i in range(60):
            staff = Staff(
                restaurant_id=test_user.restaurant_id,
                name=f"Staff {i+1}",
                email=f"staff{i+1}@test.com",
                phone=f"+1234567{i:04d}",
                is_active=True,
            )
            test_db.add(staff)

        await test_db.commit()

        # Get first page
        response = await async_client.get(
            "/api/v1/schedule/preview/paginated",
            params={
                "start_date": date.today().isoformat(),
                "end_date": date.today().isoformat(),
                "page": 1,
                "page_size": 20,
            },
            headers={"Authorization": f"Bearer {test_user.token}"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["page"] == 1
        assert data["page_size"] == 20
        assert data["total_items"] == 60
        assert data["total_pages"] == 3
        assert len(data["items"]) == 20

        # Get second page
        response2 = await async_client.get(
            "/api/v1/schedule/preview/paginated",
            params={
                "start_date": date.today().isoformat(),
                "end_date": date.today().isoformat(),
                "page": 2,
                "page_size": 20,
            },
            headers={"Authorization": f"Bearer {test_user.token}"},
        )

        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["page"] == 2
        assert len(data2["items"]) == 20

        # Verify different staff on different pages
        page1_ids = {item["staff_id"] for item in data["items"]}
        page2_ids = {item["staff_id"] for item in data2["items"]}
        assert page1_ids.isdisjoint(page2_ids)

    @pytest.mark.asyncio
    async def test_preview_performance(
        self, async_client: AsyncClient, test_db: AsyncSession, test_user
    ):
        """Test preview performance with large dataset"""
        import time

        # Create 100 staff with schedules
        staff_members = []
        for i in range(100):
            staff = Staff(
                restaurant_id=test_user.restaurant_id,
                name=f"Staff {i+1}",
                email=f"staff{i+1}@test.com",
                phone=f"+1234567{i:04d}",
                is_active=True,
            )
            test_db.add(staff)
            staff_members.append(staff)

        await test_db.flush()

        # Create 7 days of schedules for each staff
        for day in range(7):
            for staff in staff_members:
                schedule = Schedule(
                    restaurant_id=test_user.restaurant_id,
                    staff_id=staff.id,
                    date=date.today() + timedelta(days=day),
                    start_time="09:00",
                    end_time="17:00",
                    is_published=False,
                )
                test_db.add(schedule)

        await test_db.commit()

        # Time the preview generation
        start_time = time.time()

        response = await async_client.get(
            "/api/v1/schedule/preview",
            params={
                "start_date": date.today().isoformat(),
                "end_date": (date.today() + timedelta(days=6)).isoformat(),
                "use_cache": "false",  # Force fresh generation
            },
            headers={"Authorization": f"Bearer {test_user.token}"},
        )

        end_time = time.time()
        duration = end_time - start_time

        assert response.status_code == 200
        data = response.json()
        assert data["total_shifts"] == 700  # 100 staff * 7 days

        # Should complete within reasonable time even with large dataset
        assert duration < 5.0  # 5 seconds max

        # Second request with cache should be much faster
        cache_start = time.time()

        response2 = await async_client.get(
            "/api/v1/schedule/preview",
            params={
                "start_date": date.today().isoformat(),
                "end_date": (date.today() + timedelta(days=6)).isoformat(),
            },
            headers={"Authorization": f"Bearer {test_user.token}"},
        )

        cache_end = time.time()
        cache_duration = cache_end - cache_start

        assert response2.status_code == 200
        assert cache_duration < 0.5  # Cache hit should be under 500ms
