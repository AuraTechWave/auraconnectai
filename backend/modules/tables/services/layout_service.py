# backend/modules/tables/services/layout_service.py

from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
import logging
import json
import csv
from io import StringIO
import qrcode
import base64
from io import BytesIO

from ..models.table_models import Floor, Table, TableLayout, FloorStatus, TableStatus
from ..schemas.table_schemas import (
    FloorCreate, FloorUpdate, TableCreate, TableUpdate,
    BulkTableCreate, BulkTableUpdate, TableLayoutCreate, TableLayoutUpdate
)
from core.exceptions import ConflictError as BusinessLogicError, NotFoundError as ResourceNotFoundError

logger = logging.getLogger(__name__)


class LayoutService:
    """Service for managing table layouts and floor plans"""
    
    async def create_floor(
        self,
        db: AsyncSession,
        restaurant_id: int,
        floor_data: FloorCreate
    ) -> Floor:
        """Create a new floor"""
        
        # Check if floor name already exists
        existing = await db.execute(
            select(Floor).where(
                and_(
                    Floor.restaurant_id == restaurant_id,
                    Floor.name == floor_data.name
                )
            )
        )
        if existing.scalar():
            raise BusinessLogicError(f"Floor with name '{floor_data.name}' already exists")
        
        # If setting as default, unset other defaults
        if floor_data.is_default:
            await self._unset_default_floors(db, restaurant_id)
        
        floor = Floor(
            restaurant_id=restaurant_id,
            **floor_data.dict()
        )
        
        db.add(floor)
        await db.commit()
        await db.refresh(floor)
        
        return floor
    
    async def get_floors(
        self,
        db: AsyncSession,
        restaurant_id: int,
        include_inactive: bool = False
    ) -> List[Floor]:
        """Get all floors for restaurant"""
        
        query = select(Floor).where(
            Floor.restaurant_id == restaurant_id
        ).options(selectinload(Floor.tables))
        
        if not include_inactive:
            query = query.where(Floor.status == FloorStatus.ACTIVE)
        
        query = query.order_by(Floor.floor_number, Floor.name)
        
        result = await db.execute(query)
        floors = result.scalars().all()
        
        # Add table counts
        for floor in floors:
            floor.table_count = len(floor.tables)
            floor.occupied_tables = len([
                t for t in floor.tables 
                if t.status == TableStatus.OCCUPIED
            ])
        
        return floors
    
    async def get_floor(
        self,
        db: AsyncSession,
        restaurant_id: int,
        floor_id: int
    ) -> Floor:
        """Get floor by ID"""
        
        floor = await self._get_floor(db, floor_id, restaurant_id)
        
        # Load tables
        await db.refresh(floor, ['tables'])
        
        floor.table_count = len(floor.tables)
        floor.occupied_tables = len([
            t for t in floor.tables 
            if t.status == TableStatus.OCCUPIED
        ])
        
        return floor
    
    async def update_floor(
        self,
        db: AsyncSession,
        restaurant_id: int,
        floor_id: int,
        update_data: FloorUpdate
    ) -> Floor:
        """Update floor details"""
        
        floor = await self._get_floor(db, floor_id, restaurant_id)
        
        # Check name uniqueness if changed
        if update_data.name and update_data.name != floor.name:
            existing = await db.execute(
                select(Floor).where(
                    and_(
                        Floor.restaurant_id == restaurant_id,
                        Floor.name == update_data.name,
                        Floor.id != floor_id
                    )
                )
            )
            if existing.scalar():
                raise BusinessLogicError(f"Floor with name '{update_data.name}' already exists")
        
        # Handle default flag
        if update_data.is_default and not floor.is_default:
            await self._unset_default_floors(db, restaurant_id)
        
        # Update fields
        for field, value in update_data.dict(exclude_unset=True).items():
            setattr(floor, field, value)
        
        await db.commit()
        await db.refresh(floor)
        
        return floor
    
    async def delete_floor(
        self,
        db: AsyncSession,
        restaurant_id: int,
        floor_id: int,
        force: bool = False
    ) -> None:
        """Delete a floor"""
        
        floor = await self._get_floor(db, floor_id, restaurant_id)
        
        # Check if floor has tables
        table_count = await db.execute(
            select(func.count()).select_from(Table).where(
                Table.floor_id == floor_id
            )
        )
        count = table_count.scalar()
        
        if count > 0 and not force:
            raise BusinessLogicError(
                f"Floor has {count} tables. Use force=true to delete anyway."
            )
        
        await db.delete(floor)
        await db.commit()
    
    async def create_table(
        self,
        db: AsyncSession,
        restaurant_id: int,
        table_data: TableCreate
    ) -> Table:
        """Create a new table"""
        
        # Validate floor
        await self._get_floor(db, table_data.floor_id, restaurant_id)
        
        # Check table number uniqueness
        existing = await db.execute(
            select(Table).where(
                and_(
                    Table.restaurant_id == restaurant_id,
                    Table.table_number == table_data.table_number
                )
            )
        )
        if existing.scalar():
            raise BusinessLogicError(
                f"Table number '{table_data.table_number}' already exists"
            )
        
        # Validate capacity
        if table_data.min_capacity > table_data.max_capacity:
            raise BusinessLogicError("Minimum capacity cannot exceed maximum capacity")
        
        table = Table(
            restaurant_id=restaurant_id,
            **table_data.dict()
        )
        
        db.add(table)
        await db.commit()
        await db.refresh(table, ['floor'])
        
        table.floor_name = table.floor.name
        
        return table
    
    async def bulk_create_tables(
        self,
        db: AsyncSession,
        restaurant_id: int,
        bulk_data: BulkTableCreate
    ) -> List[Table]:
        """Create multiple tables at once"""
        
        # Validate floor
        await self._get_floor(db, bulk_data.floor_id, restaurant_id)
        
        # Check all table numbers are unique
        table_numbers = [t.table_number for t in bulk_data.tables]
        if len(table_numbers) != len(set(table_numbers)):
            raise BusinessLogicError("Duplicate table numbers in bulk create")
        
        # Check against existing tables
        existing = await db.execute(
            select(Table.table_number).where(
                and_(
                    Table.restaurant_id == restaurant_id,
                    Table.table_number.in_(table_numbers)
                )
            )
        )
        existing_numbers = [row[0] for row in existing]
        
        if existing_numbers:
            raise BusinessLogicError(
                f"Table numbers already exist: {', '.join(existing_numbers)}"
            )
        
        # Create tables
        tables = []
        for table_data in bulk_data.tables:
            table_dict = table_data.dict()
            table_dict['floor_id'] = bulk_data.floor_id
            
            table = Table(
                restaurant_id=restaurant_id,
                **table_dict
            )
            db.add(table)
            tables.append(table)
        
        await db.commit()
        
        # Refresh all tables
        for table in tables:
            await db.refresh(table, ['floor'])
            table.floor_name = table.floor.name
        
        return tables
    
    async def get_tables(
        self,
        db: AsyncSession,
        restaurant_id: int,
        floor_id: Optional[int] = None,
        section: Optional[str] = None,
        status: Optional[str] = None,
        include_inactive: bool = False
    ) -> List[Table]:
        """Get tables with filters"""
        
        query = select(Table).where(
            Table.restaurant_id == restaurant_id
        ).options(
            selectinload(Table.floor),
            selectinload(Table.current_session)
        )
        
        if floor_id:
            query = query.where(Table.floor_id == floor_id)
        if section:
            query = query.where(Table.section == section)
        if status:
            query = query.where(Table.status == status)
        if not include_inactive:
            query = query.where(Table.is_active == True)
        
        query = query.order_by(Table.floor_id, Table.table_number)
        
        result = await db.execute(query)
        tables = result.scalars().all()
        
        # Add floor name
        for table in tables:
            table.floor_name = table.floor.name if table.floor else None
        
        return tables
    
    async def get_table(
        self,
        db: AsyncSession,
        restaurant_id: int,
        table_id: int
    ) -> Table:
        """Get table by ID"""
        
        table = await self._get_table(db, table_id, restaurant_id)
        await db.refresh(table, ['floor', 'current_session'])
        
        table.floor_name = table.floor.name if table.floor else None
        
        return table
    
    async def update_table(
        self,
        db: AsyncSession,
        restaurant_id: int,
        table_id: int,
        update_data: TableUpdate
    ) -> Table:
        """Update table details"""
        
        table = await self._get_table(db, table_id, restaurant_id)
        
        # Validate floor if changing
        if update_data.floor_id and update_data.floor_id != table.floor_id:
            await self._get_floor(db, update_data.floor_id, restaurant_id)
        
        # Check table number uniqueness if changed
        if update_data.table_number and update_data.table_number != table.table_number:
            existing = await db.execute(
                select(Table).where(
                    and_(
                        Table.restaurant_id == restaurant_id,
                        Table.table_number == update_data.table_number,
                        Table.id != table_id
                    )
                )
            )
            if existing.scalar():
                raise BusinessLogicError(
                    f"Table number '{update_data.table_number}' already exists"
                )
        
        # Update fields
        for field, value in update_data.dict(exclude_unset=True).items():
            setattr(table, field, value)
        
        await db.commit()
        await db.refresh(table, ['floor'])
        
        table.floor_name = table.floor.name if table.floor else None
        
        return table
    
    async def bulk_update_tables(
        self,
        db: AsyncSession,
        restaurant_id: int,
        bulk_data: BulkTableUpdate
    ) -> List[Table]:
        """Update multiple tables at once"""
        
        tables = []
        
        for table_id in bulk_data.table_ids:
            table = await self._get_table(db, table_id, restaurant_id)
            
            # Apply updates
            for field, value in bulk_data.update_data.dict(exclude_unset=True).items():
                setattr(table, field, value)
            
            tables.append(table)
        
        await db.commit()
        
        # Refresh all tables
        for table in tables:
            await db.refresh(table, ['floor'])
            table.floor_name = table.floor.name if table.floor else None
        
        return tables
    
    async def delete_table(
        self,
        db: AsyncSession,
        restaurant_id: int,
        table_id: int
    ) -> None:
        """Delete a table"""
        
        table = await self._get_table(db, table_id, restaurant_id)
        
        # Check if table has active session
        if table.current_session:
            raise BusinessLogicError("Cannot delete table with active session")
        
        await db.delete(table)
        await db.commit()
    
    async def create_layout(
        self,
        db: AsyncSession,
        restaurant_id: int,
        layout_data: TableLayoutCreate
    ) -> TableLayout:
        """Save a table layout configuration"""
        
        # Check name uniqueness
        existing = await db.execute(
            select(TableLayout).where(
                and_(
                    TableLayout.restaurant_id == restaurant_id,
                    TableLayout.name == layout_data.name
                )
            )
        )
        if existing.scalar():
            raise BusinessLogicError(f"Layout '{layout_data.name}' already exists")
        
        # If setting as default, unset others
        if layout_data.is_default:
            await self._unset_default_layouts(db, restaurant_id)
        
        # If activating, deactivate others
        if layout_data.is_active:
            await self._deactivate_layouts(db, restaurant_id)
        
        layout = TableLayout(
            restaurant_id=restaurant_id,
            **layout_data.dict()
        )
        
        db.add(layout)
        await db.commit()
        await db.refresh(layout)
        
        return layout
    
    async def get_layouts(
        self,
        db: AsyncSession,
        restaurant_id: int,
        include_inactive: bool = False
    ) -> List[TableLayout]:
        """Get all saved layouts"""
        
        query = select(TableLayout).where(
            TableLayout.restaurant_id == restaurant_id
        )
        
        if not include_inactive:
            query = query.where(
                TableLayout.is_active == True
            )
        
        query = query.order_by(TableLayout.created_at.desc())
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def get_active_layout(
        self,
        db: AsyncSession,
        restaurant_id: int
    ) -> Optional[TableLayout]:
        """Get currently active layout"""
        
        result = await db.execute(
            select(TableLayout).where(
                and_(
                    TableLayout.restaurant_id == restaurant_id,
                    TableLayout.is_active == True
                )
            )
        )
        
        return result.scalar_one_or_none()
    
    async def get_layout(
        self,
        db: AsyncSession,
        restaurant_id: int,
        layout_id: int
    ) -> TableLayout:
        """Get layout by ID"""
        
        layout = await self._get_layout(db, layout_id, restaurant_id)
        return layout
    
    async def update_layout(
        self,
        db: AsyncSession,
        restaurant_id: int,
        layout_id: int,
        update_data: TableLayoutUpdate
    ) -> TableLayout:
        """Update layout configuration"""
        
        layout = await self._get_layout(db, layout_id, restaurant_id)
        
        # Check name uniqueness if changed
        if update_data.name and update_data.name != layout.name:
            existing = await db.execute(
                select(TableLayout).where(
                    and_(
                        TableLayout.restaurant_id == restaurant_id,
                        TableLayout.name == update_data.name,
                        TableLayout.id != layout_id
                    )
                )
            )
            if existing.scalar():
                raise BusinessLogicError(f"Layout '{update_data.name}' already exists")
        
        # Handle default/active flags
        if update_data.is_default and not layout.is_default:
            await self._unset_default_layouts(db, restaurant_id)
        
        if update_data.is_active and not layout.is_active:
            await self._deactivate_layouts(db, restaurant_id)
        
        # Update fields
        for field, value in update_data.dict(exclude_unset=True).items():
            setattr(layout, field, value)
        
        await db.commit()
        await db.refresh(layout)
        
        return layout
    
    async def activate_layout(
        self,
        db: AsyncSession,
        restaurant_id: int,
        layout_id: int
    ) -> TableLayout:
        """Activate a saved layout"""
        
        layout = await self._get_layout(db, layout_id, restaurant_id)
        
        # Deactivate others
        await self._deactivate_layouts(db, restaurant_id)
        
        layout.is_active = True
        
        await db.commit()
        await db.refresh(layout)
        
        return layout
    
    async def apply_layout(
        self,
        db: AsyncSession,
        restaurant_id: int,
        layout_id: int
    ) -> Dict[str, Any]:
        """Apply a saved layout to actual tables"""
        
        layout = await self._get_layout(db, layout_id, restaurant_id)
        
        if not layout.layout_data:
            raise BusinessLogicError("Layout has no data to apply")
        
        # Extract table configurations from layout
        floors_data = layout.layout_data.get("floors", {})
        tables_updated = 0
        tables_created = 0
        errors = []
        
        for floor_id, floor_data in floors_data.items():
            for table_config in floor_data.get("tables", []):
                try:
                    table_number = table_config.get("table_number")
                    if not table_number:
                        continue
                    
                    # Try to find existing table
                    result = await db.execute(
                        select(Table).where(
                            and_(
                                Table.restaurant_id == restaurant_id,
                                Table.table_number == table_number
                            )
                        )
                    )
                    table = result.scalar_one_or_none()
                    
                    if table:
                        # Update existing table
                        for field in ['position_x', 'position_y', 'width', 
                                    'height', 'rotation', 'shape', 'color']:
                            if field in table_config:
                                setattr(table, field, table_config[field])
                        tables_updated += 1
                    else:
                        # Create new table
                        table = Table(
                            restaurant_id=restaurant_id,
                            floor_id=int(floor_id),
                            **table_config
                        )
                        db.add(table)
                        tables_created += 1
                        
                except Exception as e:
                    errors.append({
                        "table_number": table_config.get("table_number"),
                        "error": str(e)
                    })
        
        await db.commit()
        
        return {
            "success": len(errors) == 0,
            "tables_updated": tables_updated,
            "tables_created": tables_created,
            "errors": errors
        }
    
    async def delete_layout(
        self,
        db: AsyncSession,
        restaurant_id: int,
        layout_id: int
    ) -> None:
        """Delete a layout"""
        
        layout = await self._get_layout(db, layout_id, restaurant_id)
        
        if layout.is_active:
            raise BusinessLogicError("Cannot delete active layout")
        
        await db.delete(layout)
        await db.commit()
    
    async def export_layout(
        self,
        db: AsyncSession,
        restaurant_id: int,
        format: str = "json",
        floor_id: Optional[int] = None
    ) -> Any:
        """Export current table layout"""
        
        # Get floors and tables
        floors = await self.get_floors(db, restaurant_id, include_inactive=True)
        tables = await self.get_tables(db, restaurant_id, include_inactive=True)
        
        if floor_id:
            floors = [f for f in floors if f.id == floor_id]
            tables = [t for t in tables if t.floor_id == floor_id]
        
        if format == "json":
            export_data = {
                "restaurant_id": restaurant_id,
                "export_date": datetime.utcnow().isoformat(),
                "floors": {},
                "summary": {
                    "total_floors": len(floors),
                    "total_tables": len(tables)
                }
            }
            
            for floor in floors:
                floor_tables = [t for t in tables if t.floor_id == floor.id]
                export_data["floors"][str(floor.id)] = {
                    "floor_info": {
                        "id": floor.id,
                        "name": floor.name,
                        "floor_number": floor.floor_number,
                        "width": floor.width,
                        "height": floor.height,
                        "grid_size": floor.grid_size
                    },
                    "tables": [
                        {
                            "table_number": t.table_number,
                            "display_name": t.display_name,
                            "min_capacity": t.min_capacity,
                            "max_capacity": t.max_capacity,
                            "position_x": t.position_x,
                            "position_y": t.position_y,
                            "width": t.width,
                            "height": t.height,
                            "rotation": t.rotation,
                            "shape": t.shape,
                            "color": t.color,
                            "section": t.section,
                            "features": {
                                "has_power_outlet": t.has_power_outlet,
                                "is_wheelchair_accessible": t.is_wheelchair_accessible,
                                "is_by_window": t.is_by_window,
                                "is_private": t.is_private
                            }
                        }
                        for t in floor_tables
                    ]
                }
            
            return export_data
            
        elif format == "csv":
            output = StringIO()
            writer = csv.writer(output)
            
            # Header
            writer.writerow([
                "Floor", "Table Number", "Display Name", "Min Capacity", 
                "Max Capacity", "Position X", "Position Y", "Width", "Height",
                "Rotation", "Shape", "Section", "Power Outlet", "Wheelchair",
                "Window", "Private"
            ])
            
            # Data rows
            for table in tables:
                floor = next((f for f in floors if f.id == table.floor_id), None)
                writer.writerow([
                    floor.name if floor else "",
                    table.table_number,
                    table.display_name or "",
                    table.min_capacity,
                    table.max_capacity,
                    table.position_x,
                    table.position_y,
                    table.width,
                    table.height,
                    table.rotation,
                    table.shape,
                    table.section or "",
                    "Yes" if table.has_power_outlet else "No",
                    "Yes" if table.is_wheelchair_accessible else "No",
                    "Yes" if table.is_by_window else "No",
                    "Yes" if table.is_private else "No"
                ])
            
            return output.getvalue()
    
    async def import_layout(
        self,
        db: AsyncSession,
        restaurant_id: int,
        layout_data: Dict[str, Any],
        merge: bool = False
    ) -> Dict[str, Any]:
        """Import table layout configuration"""
        
        if not merge:
            # TODO: Clear existing layout
            logger.warning("Non-merge import not fully implemented")
        
        floors_created = 0
        tables_created = 0
        tables_updated = 0
        errors = []
        
        # Process floors
        for floor_key, floor_data in layout_data.get("floors", {}).items():
            floor_info = floor_data.get("floor_info", {})
            
            try:
                # Find or create floor
                result = await db.execute(
                    select(Floor).where(
                        and_(
                            Floor.restaurant_id == restaurant_id,
                            Floor.name == floor_info.get("name")
                        )
                    )
                )
                floor = result.scalar_one_or_none()
                
                if not floor:
                    floor = Floor(
                        restaurant_id=restaurant_id,
                        name=floor_info.get("name"),
                        floor_number=floor_info.get("floor_number", 1),
                        width=floor_info.get("width", 1000),
                        height=floor_info.get("height", 800),
                        grid_size=floor_info.get("grid_size", 20)
                    )
                    db.add(floor)
                    floors_created += 1
                    await db.flush()
                
                # Process tables
                for table_data in floor_data.get("tables", []):
                    table_number = table_data.get("table_number")
                    if not table_number:
                        continue
                    
                    # Find existing table
                    result = await db.execute(
                        select(Table).where(
                            and_(
                                Table.restaurant_id == restaurant_id,
                                Table.table_number == table_number
                            )
                        )
                    )
                    table = result.scalar_one_or_none()
                    
                    if table and merge:
                        # Update existing
                        for field, value in table_data.items():
                            if field != "features" and hasattr(table, field):
                                setattr(table, field, value)
                        
                        # Handle features
                        features = table_data.get("features", {})
                        for feature, value in features.items():
                            if hasattr(table, feature):
                                setattr(table, feature, value)
                        
                        tables_updated += 1
                    elif not table:
                        # Create new
                        table_dict = {k: v for k, v in table_data.items() 
                                    if k != "features"}
                        table_dict["floor_id"] = floor.id
                        
                        # Add features
                        features = table_data.get("features", {})
                        table_dict.update(features)
                        
                        table = Table(
                            restaurant_id=restaurant_id,
                            **table_dict
                        )
                        db.add(table)
                        tables_created += 1
                        
            except Exception as e:
                errors.append({
                    "floor": floor_info.get("name"),
                    "error": str(e)
                })
        
        await db.commit()
        
        return {
            "success": len(errors) == 0,
            "floors_created": floors_created,
            "tables_created": tables_created,
            "tables_updated": tables_updated,
            "errors": errors
        }
    
    async def generate_qr_codes(
        self,
        db: AsyncSession,
        restaurant_id: int,
        table_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """Generate QR codes for tables"""
        
        # Get tables
        query = select(Table).where(
            Table.restaurant_id == restaurant_id
        )
        
        if table_ids:
            query = query.where(Table.id.in_(table_ids))
        
        result = await db.execute(query)
        tables = result.scalars().all()
        
        updated_count = 0
        qr_codes = {}
        
        for table in tables:
            # Generate QR code data
            qr_data = f"https://restaurant.com/menu?table={table.table_number}&restaurant={restaurant_id}"
            
            # Create QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_data)
            qr.make(fit=True)
            
            # Create image
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert to base64
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            # Update table
            table.qr_code = f"data:image/png;base64,{img_str}"
            updated_count += 1
            
            qr_codes[table.table_number] = {
                "table_id": table.id,
                "qr_code": table.qr_code,
                "url": qr_data
            }
        
        await db.commit()
        
        return {
            "success": True,
            "updated_count": updated_count,
            "qr_codes": qr_codes
        }
    
    async def validate_layout(
        self,
        db: AsyncSession,
        restaurant_id: int
    ) -> List[Dict[str, Any]]:
        """Validate current layout for issues"""
        
        issues = []
        
        # Get all tables
        tables = await self.get_tables(db, restaurant_id, include_inactive=True)
        
        # Check for duplicate table numbers
        table_numbers = {}
        for table in tables:
            if table.table_number in table_numbers:
                issues.append({
                    "type": "duplicate_table_number",
                    "severity": "error",
                    "table_ids": [table_numbers[table.table_number], table.id],
                    "message": f"Duplicate table number: {table.table_number}"
                })
            table_numbers[table.table_number] = table.id
        
        # Check for overlapping tables
        floors = {}
        for table in tables:
            if table.floor_id not in floors:
                floors[table.floor_id] = []
            floors[table.floor_id].append(table)
        
        for floor_id, floor_tables in floors.items():
            for i, table1 in enumerate(floor_tables):
                for table2 in floor_tables[i+1:]:
                    if self._tables_overlap(table1, table2):
                        issues.append({
                            "type": "overlapping_tables",
                            "severity": "warning",
                            "table_ids": [table1.id, table2.id],
                            "message": f"Tables {table1.table_number} and {table2.table_number} overlap"
                        })
        
        # Check for tables outside floor bounds
        floor_list = await self.get_floors(db, restaurant_id, include_inactive=True)
        floor_map = {f.id: f for f in floor_list}
        
        for table in tables:
            floor = floor_map.get(table.floor_id)
            if floor:
                if (table.position_x + table.width > floor.width or
                    table.position_y + table.height > floor.height):
                    issues.append({
                        "type": "table_out_of_bounds",
                        "severity": "warning",
                        "table_id": table.id,
                        "message": f"Table {table.table_number} extends outside floor bounds"
                    })
        
        # Check for invalid capacities
        for table in tables:
            if table.min_capacity > table.max_capacity:
                issues.append({
                    "type": "invalid_capacity",
                    "severity": "error",
                    "table_id": table.id,
                    "message": f"Table {table.table_number} has min capacity > max capacity"
                })
        
        return issues
    
    def _tables_overlap(self, table1: Table, table2: Table) -> bool:
        """Check if two tables overlap"""
        
        # Simple rectangle overlap check
        return not (
            table1.position_x + table1.width <= table2.position_x or
            table2.position_x + table2.width <= table1.position_x or
            table1.position_y + table1.height <= table2.position_y or
            table2.position_y + table2.height <= table1.position_y
        )
    
    async def _get_floor(
        self,
        db: AsyncSession,
        floor_id: int,
        restaurant_id: int
    ) -> Floor:
        """Get floor with validation"""
        
        result = await db.execute(
            select(Floor).where(
                and_(
                    Floor.id == floor_id,
                    Floor.restaurant_id == restaurant_id
                )
            )
        )
        floor = result.scalar_one_or_none()
        
        if not floor:
            raise ResourceNotFoundError(f"Floor {floor_id} not found")
        
        return floor
    
    async def _get_table(
        self,
        db: AsyncSession,
        table_id: int,
        restaurant_id: int
    ) -> Table:
        """Get table with validation"""
        
        result = await db.execute(
            select(Table).where(
                and_(
                    Table.id == table_id,
                    Table.restaurant_id == restaurant_id
                )
            )
        )
        table = result.scalar_one_or_none()
        
        if not table:
            raise ResourceNotFoundError(f"Table {table_id} not found")
        
        return table
    
    async def _get_layout(
        self,
        db: AsyncSession,
        layout_id: int,
        restaurant_id: int
    ) -> TableLayout:
        """Get layout with validation"""
        
        result = await db.execute(
            select(TableLayout).where(
                and_(
                    TableLayout.id == layout_id,
                    TableLayout.restaurant_id == restaurant_id
                )
            )
        )
        layout = result.scalar_one_or_none()
        
        if not layout:
            raise ResourceNotFoundError(f"Layout {layout_id} not found")
        
        return layout
    
    async def _unset_default_floors(
        self,
        db: AsyncSession,
        restaurant_id: int
    ):
        """Unset all default floors"""
        
        await db.execute(
            select(Floor).where(
                and_(
                    Floor.restaurant_id == restaurant_id,
                    Floor.is_default == True
                )
            ).execution_options(synchronize_session="fetch")
        )
        
        result = await db.execute(
            select(Floor).where(
                and_(
                    Floor.restaurant_id == restaurant_id,
                    Floor.is_default == True
                )
            )
        )
        
        for floor in result.scalars():
            floor.is_default = False
    
    async def _unset_default_layouts(
        self,
        db: AsyncSession,
        restaurant_id: int
    ):
        """Unset all default layouts"""
        
        result = await db.execute(
            select(TableLayout).where(
                and_(
                    TableLayout.restaurant_id == restaurant_id,
                    TableLayout.is_default == True
                )
            )
        )
        
        for layout in result.scalars():
            layout.is_default = False
    
    async def _deactivate_layouts(
        self,
        db: AsyncSession,
        restaurant_id: int
    ):
        """Deactivate all layouts"""
        
        result = await db.execute(
            select(TableLayout).where(
                and_(
                    TableLayout.restaurant_id == restaurant_id,
                    TableLayout.is_active == True
                )
            )
        )
        
        for layout in result.scalars():
            layout.is_active = False


# Create singleton service
layout_service = LayoutService()