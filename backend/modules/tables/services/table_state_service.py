# backend/modules/tables/services/table_state_service.py

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, case
from sqlalchemy.orm import selectinload
import logging
from decimal import Decimal

from ..models.table_models import (
    Table, TableSession, TableCombination, TableReservation, 
    TableStateLog, Floor, TableStatus, ReservationStatus
)
from ..schemas.table_schemas import (
    TableSessionCreate, TableSessionUpdate, TableStatusUpdate,
    BulkTableStatusUpdate, TableReservationCreate
)
from core.exceptions import ConflictError as BusinessLogicError, NotFoundError as ResourceNotFoundError

logger = logging.getLogger(__name__)


class TableStateService:
    """Service for managing table states and sessions"""
    
    async def get_table_availability(
        self,
        db: AsyncSession,
        restaurant_id: int,
        datetime_from: datetime,
        datetime_to: datetime,
        guest_count: Optional[int] = None,
        floor_id: Optional[int] = None,
        section: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get available tables for a time range"""
        
        # Get all active tables
        query = select(Table).where(
            and_(
                Table.restaurant_id == restaurant_id,
                Table.is_active == True
            )
        )
        
        if floor_id:
            query = query.where(Table.floor_id == floor_id)
        if section:
            query = query.where(Table.section == section)
        if guest_count:
            query = query.where(
                and_(
                    Table.min_capacity <= guest_count,
                    Table.max_capacity >= guest_count
                )
            )
        
        result = await db.execute(query)
        tables = result.scalars().all()
        
        available_tables = []
        
        for table in tables:
            # Check if table is available in the time range
            is_available = await self._is_table_available(
                db, table.id, datetime_from, datetime_to
            )
            
            if is_available:
                available_tables.append({
                    "table_id": table.id,
                    "table_number": table.table_number,
                    "floor_id": table.floor_id,
                    "section": table.section,
                    "min_capacity": table.min_capacity,
                    "max_capacity": table.max_capacity,
                    "current_status": table.status,
                    "features": {
                        "has_power_outlet": table.has_power_outlet,
                        "is_wheelchair_accessible": table.is_wheelchair_accessible,
                        "is_by_window": table.is_by_window,
                        "is_private": table.is_private
                    }
                })
        
        return available_tables
    
    async def _is_table_available(
        self,
        db: AsyncSession,
        table_id: int,
        datetime_from: datetime,
        datetime_to: datetime
    ) -> bool:
        """Check if a table is available in a time range"""
        
        # Check for overlapping reservations
        reservation_query = select(TableReservation).where(
            and_(
                TableReservation.table_id == table_id,
                TableReservation.status.in_([
                    ReservationStatus.PENDING,
                    ReservationStatus.CONFIRMED,
                    ReservationStatus.SEATED
                ]),
                or_(
                    # Reservation starts during our range
                    and_(
                        TableReservation.reservation_date >= datetime_from,
                        TableReservation.reservation_date < datetime_to
                    ),
                    # Reservation ends during our range
                    and_(
                        TableReservation.reservation_date < datetime_from,
                        func.datetime(
                            TableReservation.reservation_date,
                            func.concat('+', TableReservation.duration_minutes, ' minutes')
                        ) > datetime_from
                    )
                )
            )
        )
        
        result = await db.execute(reservation_query)
        if result.scalar():
            return False
        
        # Check for active sessions (if checking current time)
        if datetime_from <= datetime.utcnow() <= datetime_to:
            session_query = select(TableSession).where(
                and_(
                    TableSession.table_id == table_id,
                    TableSession.end_time.is_(None)
                )
            )
            result = await db.execute(session_query)
            if result.scalar():
                return False
        
        return True
    
    async def start_table_session(
        self,
        db: AsyncSession,
        restaurant_id: int,
        session_data: TableSessionCreate,
        user_id: int
    ) -> TableSession:
        """Start a new table session"""
        
        # Validate table exists and is available
        table = await self._get_table(db, session_data.table_id, restaurant_id)
        
        if table.status != TableStatus.AVAILABLE:
            raise BusinessLogicError(
                f"Table {table.table_number} is not available. Current status: {table.status}"
            )
        
        # Check guest count
        if session_data.guest_count > table.max_capacity:
            raise BusinessLogicError(
                f"Guest count ({session_data.guest_count}) exceeds table capacity ({table.max_capacity})"
            )
        
        # Handle combined tables if needed
        combined_tables = []
        if session_data.combined_table_ids:
            combined_tables = await self._validate_combined_tables(
                db, restaurant_id, session_data.combined_table_ids, session_data.table_id
            )
        
        # Create session
        session = TableSession(
            restaurant_id=restaurant_id,
            table_id=session_data.table_id,
            guest_count=session_data.guest_count,
            guest_name=session_data.guest_name,
            guest_phone=session_data.guest_phone,
            server_id=session_data.server_id
        )
        
        db.add(session)
        await db.flush()
        
        # Create combinations
        if combined_tables:
            # Primary table
            primary_combination = TableCombination(
                session_id=session.id,
                table_id=session_data.table_id,
                is_primary=True
            )
            db.add(primary_combination)
            
            # Additional tables
            for table_id in combined_tables:
                combination = TableCombination(
                    session_id=session.id,
                    table_id=table_id,
                    is_primary=False
                )
                db.add(combination)
        
        # Update table status
        await self._update_table_status(
            db, table, TableStatus.OCCUPIED, user_id, 
            session_id=session.id, reason="Session started"
        )
        
        # Update combined tables status
        for table_id in combined_tables:
            combined_table = await self._get_table(db, table_id, restaurant_id)
            await self._update_table_status(
                db, combined_table, TableStatus.OCCUPIED, user_id,
                session_id=session.id, reason="Part of combined seating"
            )
        
        await db.commit()
        await db.refresh(session)
        
        return session
    
    async def _validate_combined_tables(
        self,
        db: AsyncSession,
        restaurant_id: int,
        table_ids: List[int],
        primary_table_id: int
    ) -> List[int]:
        """Validate tables can be combined"""
        
        valid_ids = []
        
        for table_id in table_ids:
            if table_id == primary_table_id:
                continue
                
            table = await self._get_table(db, table_id, restaurant_id)
            
            if not table.is_combinable:
                raise BusinessLogicError(f"Table {table.table_number} cannot be combined")
            
            if table.status != TableStatus.AVAILABLE:
                raise BusinessLogicError(
                    f"Table {table.table_number} is not available for combining"
                )
            
            valid_ids.append(table_id)
        
        return valid_ids
    
    async def end_table_session(
        self,
        db: AsyncSession,
        restaurant_id: int,
        session_id: int,
        user_id: int
    ) -> TableSession:
        """End a table session"""
        
        # Get session with combined tables
        query = select(TableSession).where(
            and_(
                TableSession.id == session_id,
                TableSession.restaurant_id == restaurant_id,
                TableSession.end_time.is_(None)
            )
        ).options(selectinload(TableSession.combined_tables))
        
        result = await db.execute(query)
        session = result.scalar_one_or_none()
        
        if not session:
            raise ResourceNotFoundError("Active session not found")
        
        # End session
        session.end_time = datetime.utcnow()
        
        # Get all tables involved
        table_ids = [session.table_id]
        table_ids.extend([c.table_id for c in session.combined_tables if not c.is_primary])
        
        # Update all tables to available
        for table_id in table_ids:
            table = await self._get_table(db, table_id, restaurant_id)
            await self._update_table_status(
                db, table, TableStatus.AVAILABLE, user_id,
                session_id=session_id, reason="Session ended"
            )
        
        await db.commit()
        await db.refresh(session)
        
        return session
    
    async def update_table_status(
        self,
        db: AsyncSession,
        restaurant_id: int,
        table_id: int,
        status_update: TableStatusUpdate,
        user_id: int
    ) -> Table:
        """Update single table status"""
        
        table = await self._get_table(db, table_id, restaurant_id)
        
        # Validate status transition
        self._validate_status_transition(table.status, status_update.status)
        
        await self._update_table_status(
            db, table, status_update.status, user_id,
            reason=status_update.reason
        )
        
        await db.commit()
        await db.refresh(table)
        
        return table
    
    async def bulk_update_table_status(
        self,
        db: AsyncSession,
        restaurant_id: int,
        bulk_update: BulkTableStatusUpdate,
        user_id: int
    ) -> List[Table]:
        """Update multiple tables status"""
        
        updated_tables = []
        
        for table_id in bulk_update.table_ids:
            table = await self._get_table(db, table_id, restaurant_id)
            
            # Skip if already in target status
            if table.status == bulk_update.status:
                continue
            
            # Validate transition
            try:
                self._validate_status_transition(table.status, bulk_update.status)
            except BusinessLogicError as e:
                logger.warning(f"Skipping table {table.table_number}: {e}")
                continue
            
            await self._update_table_status(
                db, table, bulk_update.status, user_id,
                reason=bulk_update.reason
            )
            
            updated_tables.append(table)
        
        await db.commit()
        
        return updated_tables
    
    async def _update_table_status(
        self,
        db: AsyncSession,
        table: Table,
        new_status: TableStatus,
        user_id: int,
        session_id: Optional[int] = None,
        reservation_id: Optional[int] = None,
        reason: Optional[str] = None
    ):
        """Internal method to update table status and log change"""
        
        if table.status == new_status:
            return
        
        # Calculate duration in previous status
        last_log_query = select(TableStateLog).where(
            and_(
                TableStateLog.table_id == table.id,
                TableStateLog.new_status == table.status
            )
        ).order_by(TableStateLog.changed_at.desc()).limit(1)
        
        result = await db.execute(last_log_query)
        last_log = result.scalar_one_or_none()
        
        duration_minutes = None
        if last_log:
            duration = datetime.utcnow() - last_log.changed_at
            duration_minutes = int(duration.total_seconds() / 60)
        
        # Create log entry
        log = TableStateLog(
            restaurant_id=table.restaurant_id,
            table_id=table.id,
            previous_status=table.status,
            new_status=new_status,
            changed_by_id=user_id,
            session_id=session_id,
            reservation_id=reservation_id,
            reason=reason,
            duration_minutes=duration_minutes
        )
        
        db.add(log)
        
        # Update table status
        table.status = new_status
    
    def _validate_status_transition(
        self,
        current_status: TableStatus,
        new_status: TableStatus
    ):
        """Validate if status transition is allowed"""
        
        # Define allowed transitions
        allowed_transitions = {
            TableStatus.AVAILABLE: [
                TableStatus.OCCUPIED,
                TableStatus.RESERVED,
                TableStatus.BLOCKED,
                TableStatus.CLEANING,
                TableStatus.MAINTENANCE
            ],
            TableStatus.OCCUPIED: [
                TableStatus.AVAILABLE,
                TableStatus.CLEANING
            ],
            TableStatus.RESERVED: [
                TableStatus.OCCUPIED,
                TableStatus.AVAILABLE,
                TableStatus.BLOCKED
            ],
            TableStatus.BLOCKED: [
                TableStatus.AVAILABLE,
                TableStatus.MAINTENANCE
            ],
            TableStatus.CLEANING: [
                TableStatus.AVAILABLE,
                TableStatus.MAINTENANCE
            ],
            TableStatus.MAINTENANCE: [
                TableStatus.AVAILABLE
            ]
        }
        
        if new_status not in allowed_transitions.get(current_status, []):
            raise BusinessLogicError(
                f"Invalid status transition from {current_status} to {new_status}"
            )
    
    async def _get_table(
        self,
        db: AsyncSession,
        table_id: int,
        restaurant_id: int
    ) -> Table:
        """Get table by ID with validation"""
        
        query = select(Table).where(
            and_(
                Table.id == table_id,
                Table.restaurant_id == restaurant_id
            )
        )
        
        result = await db.execute(query)
        table = result.scalar_one_or_none()
        
        if not table:
            raise ResourceNotFoundError(f"Table with ID {table_id} not found")
        
        return table
    
    async def get_floor_status(
        self,
        db: AsyncSession,
        restaurant_id: int,
        floor_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get current status of all tables on floor(s)"""
        
        query = select(Table).where(
            and_(
                Table.restaurant_id == restaurant_id,
                Table.is_active == True
            )
        ).options(
            selectinload(Table.current_session).selectinload(TableSession.server),
            selectinload(Table.floor)
        )
        
        if floor_id:
            query = query.where(Table.floor_id == floor_id)
        
        result = await db.execute(query)
        tables = result.scalars().all()
        
        # Group by floor
        floors_data = {}
        
        for table in tables:
            floor_key = table.floor_id
            
            if floor_key not in floors_data:
                floors_data[floor_key] = {
                    "floor_id": table.floor.id,
                    "floor_name": table.floor.name,
                    "total_tables": 0,
                    "available_tables": 0,
                    "occupied_tables": 0,
                    "reserved_tables": 0,
                    "blocked_tables": 0,
                    "tables": []
                }
            
            floor_data = floors_data[floor_key]
            floor_data["total_tables"] += 1
            
            # Count by status
            if table.status == TableStatus.AVAILABLE:
                floor_data["available_tables"] += 1
            elif table.status == TableStatus.OCCUPIED:
                floor_data["occupied_tables"] += 1
            elif table.status == TableStatus.RESERVED:
                floor_data["reserved_tables"] += 1
            elif table.status in [TableStatus.BLOCKED, TableStatus.CLEANING, TableStatus.MAINTENANCE]:
                floor_data["blocked_tables"] += 1
            
            # Table details
            table_data = {
                "table_id": table.id,
                "table_number": table.table_number,
                "status": table.status,
                "capacity": {
                    "min": table.min_capacity,
                    "max": table.max_capacity,
                    "preferred": table.preferred_capacity
                },
                "position": {
                    "x": table.position_x,
                    "y": table.position_y,
                    "width": table.width,
                    "height": table.height,
                    "rotation": table.rotation
                },
                "visual": {
                    "shape": table.shape,
                    "color": table.color
                }
            }
            
            # Add session info if occupied
            if table.current_session:
                session = table.current_session
                duration = (datetime.utcnow() - session.start_time).total_seconds() / 60
                
                table_data["session"] = {
                    "session_id": session.id,
                    "guest_count": session.guest_count,
                    "guest_name": session.guest_name,
                    "duration_minutes": int(duration),
                    "server_name": session.server.name if session.server else None,
                    "order_id": session.order_id
                }
            
            floor_data["tables"].append(table_data)
        
        return list(floors_data.values())
    
    async def get_table_analytics(
        self,
        db: AsyncSession,
        restaurant_id: int,
        start_date: datetime,
        end_date: datetime,
        table_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get table utilization analytics"""
        
        # Base query for sessions
        query = select(
            TableSession.table_id,
            func.count(TableSession.id).label('session_count'),
            func.sum(TableSession.guest_count).label('total_guests'),
            func.avg(
                func.extract('epoch', TableSession.end_time - TableSession.start_time) / 60
            ).label('avg_duration_minutes')
        ).where(
            and_(
                TableSession.restaurant_id == restaurant_id,
                TableSession.start_time >= start_date,
                TableSession.start_time <= end_date,
                TableSession.end_time.isnot(None)
            )
        ).group_by(TableSession.table_id)
        
        if table_id:
            query = query.where(TableSession.table_id == table_id)
        
        result = await db.execute(query)
        analytics_data = result.all()
        
        # Get table info
        table_query = select(Table).where(
            Table.restaurant_id == restaurant_id
        )
        if table_id:
            table_query = table_query.where(Table.id == table_id)
        
        table_result = await db.execute(table_query)
        tables = {t.id: t for t in table_result.scalars().all()}
        
        # Process analytics
        analytics = []
        
        for row in analytics_data:
            table = tables.get(row.table_id)
            if not table:
                continue
            
            # Calculate occupancy rate
            total_minutes = (end_date - start_date).total_seconds() / 60
            occupied_minutes = row.session_count * (row.avg_duration_minutes or 0)
            occupancy_rate = (occupied_minutes / total_minutes) * 100 if total_minutes > 0 else 0
            
            analytics.append({
                "table_id": row.table_id,
                "table_number": table.table_number,
                "total_sessions": row.session_count,
                "total_guests": row.total_guests or 0,
                "avg_session_duration": round(row.avg_duration_minutes or 0, 2),
                "avg_guests_per_session": round(
                    (row.total_guests or 0) / row.session_count if row.session_count > 0 else 0,
                    2
                ),
                "occupancy_rate": round(occupancy_rate, 2)
            })
        
        # Summary statistics
        total_sessions = sum(a["total_sessions"] for a in analytics)
        total_guests = sum(a["total_guests"] for a in analytics)
        
        return {
            "period": {
                "start": start_date,
                "end": end_date
            },
            "summary": {
                "total_sessions": total_sessions,
                "total_guests": total_guests,
                "avg_occupancy_rate": round(
                    sum(a["occupancy_rate"] for a in analytics) / len(analytics)
                    if analytics else 0,
                    2
                )
            },
            "table_analytics": analytics
        }


# Create singleton service
table_state_service = TableStateService()