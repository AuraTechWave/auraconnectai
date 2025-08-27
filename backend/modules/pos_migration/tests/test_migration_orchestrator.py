# backend/modules/pos_migration/tests/test_migration_orchestrator.py

"""
Test suite for the migration orchestrator service.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from ..services import MigrationOrchestrator
from ..schemas.migration_schemas import (
    MigrationOptions,
    POSConnectionConfig,
    MigrationPhase,
    MigrationPlan,
    FieldMapping,
    FieldTransformationType,
    ValidationReport,
    MigrationComplexity,
)


@pytest.fixture
def db_session():
    """Mock database session"""
    session = MagicMock(spec=Session)
    session.info = {"tenant_id": "test-tenant-123"}
    return session


@pytest.fixture
def orchestrator(db_session):
    """Create orchestrator instance with mocked dependencies"""
    with patch('modules.pos_migration.services.migration_orchestrator.MigrationCoachAgent'):
        with patch('modules.pos_migration.services.migration_orchestrator.DataTransformationService'):
            with patch('modules.pos_migration.services.migration_orchestrator.AuditService'):
                with patch('modules.pos_migration.services.migration_orchestrator.NotificationService'):
                    return MigrationOrchestrator(db_session)


@pytest.fixture
def pos_config():
    """Sample POS configuration"""
    return POSConnectionConfig(
        pos_type="square",
        credentials={
            "access_token": "test-token",
            "location_id": "test-location"
        },
        test_mode=True
    )


@pytest.fixture
def migration_options():
    """Sample migration options"""
    return MigrationOptions(
        import_historical_data=True,
        historical_days=30,
        import_customer_data=False,
        require_consent=False,
        validate_pricing=True,
        use_ai_assistance=True,
        ai_confidence_threshold=0.7,
        batch_size=50
    )


class TestMigrationOrchestrator:
    
    @pytest.mark.asyncio
    async def test_initiate_migration(self, orchestrator, pos_config, migration_options):
        """Test initiating a new migration"""
        
        # Mock the async task creation
        with patch('asyncio.create_task'):
            migration_id = await orchestrator.initiate_migration(
                tenant_id="test-tenant",
                pos_config=pos_config,
                options=migration_options,
                user_id="test-user"
            )
        
        assert migration_id is not None
        assert migration_id in orchestrator.active_migrations
        assert orchestrator.active_migrations[migration_id].phase == MigrationPhase.SETUP
    
    @pytest.mark.asyncio
    async def test_setup_pos_connection_success(self, orchestrator, pos_config):
        """Test successful POS connection setup"""
        
        # Mock adapter factory
        mock_adapter = AsyncMock()
        mock_adapter.test_connection.return_value = True
        
        with patch('modules.pos.adapters.adapter_factory.AdapterFactory.create_adapter', return_value=mock_adapter):
            with patch('modules.pos_migration.adapters.MigrationAdapterWrapper') as mock_wrapper:
                mock_wrapper.return_value.test_connection = AsyncMock(return_value=True)
                
                adapter = await orchestrator._setup_pos_connection(
                    tenant_id="test-tenant",
                    pos_config=pos_config,
                    migration_id="test-migration"
                )
                
                assert adapter is not None
                mock_wrapper.return_value.test_connection.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_analyze_pos_data(self, orchestrator, migration_options):
        """Test POS data analysis"""
        
        # Mock adapter with data
        mock_adapter = AsyncMock()
        mock_adapter.fetch_menu_items.return_value = [
            {"id": "1", "name": "Burger", "price": 999},
            {"id": "2", "name": "Pizza", "price": 1299}
        ]
        mock_adapter.fetch_categories.return_value = [
            {"id": "cat1", "name": "Main Dishes"}
        ]
        mock_adapter.fetch_modifiers.return_value = [
            {"id": "mod1", "name": "Extra Cheese", "price": 150}
        ]
        
        analysis = await orchestrator._analyze_pos_data(
            pos_adapter=mock_adapter,
            pos_type="square",
            migration_id="test-migration",
            options=migration_options
        )
        
        assert analysis["statistics"]["total_items"] == 2
        assert analysis["statistics"]["total_categories"] == 1
        assert analysis["statistics"]["total_modifiers"] == 1
        assert len(analysis["menu_items"]) == 2
    
    @pytest.mark.asyncio
    async def test_create_mapping_plan_with_ai(self, orchestrator, migration_options):
        """Test creating field mapping plan with AI assistance"""
        
        analysis_results = {
            "menu_items": [{"id": "1", "name": "Test Item", "price": 999}],
            "categories": [{"id": "cat1", "name": "Category"}],
            "modifiers": []
        }
        
        # Mock AI response
        mock_plan = MigrationPlan(
            field_mappings=[
                FieldMapping(
                    source_field="name",
                    target_field="name",
                    confidence=0.95,
                    transformation=FieldTransformationType.NONE
                ),
                FieldMapping(
                    source_field="price",
                    target_field="price",
                    confidence=0.9,
                    transformation=FieldTransformationType.PARSE_DECIMAL
                )
            ],
            data_quality_issues=[],
            complexity=MigrationComplexity.SIMPLE,
            estimated_hours=2.0,
            risk_factors=[],
            recommendations=["Review price mappings"],
            confidence_score=0.9
        )
        
        orchestrator.coach_agent.analyze_pos_structure = AsyncMock(return_value=mock_plan)
        
        plan = await orchestrator._create_mapping_plan(
            analysis_results=analysis_results,
            pos_type="square",
            migration_id="test-migration",
            options=migration_options
        )
        
        assert len(plan.field_mappings) == 2
        assert plan.complexity == MigrationComplexity.SIMPLE
        assert all(m.confidence >= 0.7 for m in plan.field_mappings)
    
    @pytest.mark.asyncio
    async def test_validate_data_with_issues(self, orchestrator, migration_options):
        """Test data validation with pricing issues"""
        
        mock_adapter = AsyncMock()
        mock_adapter.fetch_menu_items.return_value = [
            {"id": "1", "name": "Item 1", "price": 0},
            {"id": "2", "name": "Item 2", "price": 99999},
            {"id": "3", "name": "Item 3", "price": 599}
        ]
        mock_adapter.pos_type = "square"
        
        mock_validation = ValidationReport(
            anomalies=[
                {
                    "type": "missing",
                    "severity": "high",
                    "affected_items": ["1"],
                    "description": "Item has zero price",
                    "suggested_action": "Set a valid price"
                },
                {
                    "type": "high_price",
                    "severity": "medium",
                    "affected_items": ["2"],
                    "description": "Unusually high price detected",
                    "suggested_action": "Verify price is correct"
                }
            ],
            summary={
                "total_issues": 2,
                "requires_manual_review": True,
                "confidence": 0.7
            }
        )
        
        orchestrator.coach_agent.validate_pricing_data = AsyncMock(return_value=mock_validation)
        
        validation_report = await orchestrator._validate_data(
            pos_adapter=mock_adapter,
            mapping_plan=MagicMock(),
            migration_id="test-migration",
            options=migration_options
        )
        
        assert validation_report.summary.total_issues == 2
        assert validation_report.summary.requires_manual_review is True
    
    @pytest.mark.asyncio
    async def test_import_data_success(self, orchestrator, migration_options):
        """Test successful data import"""
        
        mock_adapter = AsyncMock()
        mock_adapter.fetch_categories.return_value = [
            {"id": "cat1", "name": "Category 1"}
        ]
        mock_adapter.fetch_menu_items.return_value = [
            {"id": "item1", "name": "Item 1", "price": 999}
        ]
        
        mapping_plan = MagicMock()
        
        # Mock transformation service responses
        orchestrator.transformation_service.transform_and_import_batch = AsyncMock(
            return_value={
                "success_count": 1,
                "error_count": 0,
                "errors": [],
                "imported_ids": ["imported-1"]
            }
        )
        
        import_results = await orchestrator._import_data(
            pos_adapter=mock_adapter,
            mapping_plan=mapping_plan,
            tenant_id="test-tenant",
            migration_id="test-migration",
            options=migration_options
        )
        
        assert import_results["categories_imported"] == 1
        assert import_results["items_imported"] == 1
        assert len(import_results["errors"]) == 0
    
    @pytest.mark.asyncio
    async def test_get_migration_status(self, orchestrator):
        """Test getting migration status"""
        
        # Add a migration to active migrations
        from ..schemas.migration_schemas import MigrationStatus
        
        test_migration = MigrationStatus(
            migration_id="test-123",
            phase=MigrationPhase.IMPORT,
            progress_percent=75.0,
            started_at=datetime.utcnow(),
            items_processed=100,
            total_items=150
        )
        
        orchestrator.active_migrations["test-123"] = test_migration
        
        status = await orchestrator.get_migration_status("test-123")
        
        assert status.migration_id == "test-123"
        assert status.phase == MigrationPhase.IMPORT
        assert status.progress_percent == 75.0
    
    @pytest.mark.asyncio
    async def test_cancel_migration(self, orchestrator):
        """Test cancelling an active migration"""
        
        # Add a migration
        from ..schemas.migration_schemas import MigrationStatus
        
        test_migration = MigrationStatus(
            migration_id="test-cancel",
            phase=MigrationPhase.VALIDATION,
            progress_percent=50.0,
            started_at=datetime.utcnow()
        )
        
        orchestrator.active_migrations["test-cancel"] = test_migration
        
        await orchestrator.cancel_migration(
            migration_id="test-cancel",
            user_id="test-user",
            reason="User requested cancellation"
        )
        
        assert "test-cancel" not in orchestrator.active_migrations
    
    @pytest.mark.asyncio
    async def test_batch_data_processing(self, orchestrator):
        """Test data batching functionality"""
        
        data = list(range(100))
        batches = list(orchestrator._batch_data(data, batch_size=25))
        
        assert len(batches) == 4
        assert len(batches[0]) == 25
        assert len(batches[-1]) == 25
        assert batches[0] == list(range(25))
    
    def test_get_target_schema(self, orchestrator):
        """Test getting target schema"""
        
        schema = orchestrator._get_target_schema()
        
        assert "menu_item" in schema
        assert "category" in schema
        assert "modifier" in schema
        
        # Check menu item schema
        item_schema = schema["menu_item"]
        assert "id" in item_schema
        assert "name" in item_schema
        assert "price" in item_schema
        assert item_schema["price"] == "decimal"