# backend/modules/pos_migration/tests/test_migration_routes.py

"""
Test suite for migration API routes.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
import json

from ..schemas.migration_schemas import (
    MigrationStatus,
    MigrationPhase,
    ValidationReport,
    MappingSuggestion,
)


@pytest.fixture
def mock_auth():
    """Mock authentication middleware"""
    with patch('modules.auth.middleware.AuthMiddleware.verify_token'):
        with patch('modules.auth.middleware.AuthMiddleware.get_current_user') as mock_user:
            user = MagicMock()
            user.id = "test-user-id"
            user.tenant_id = "test-tenant"
            user.role = "restaurant_admin"
            mock_user.return_value = user
            yield mock_user


@pytest.fixture
def mock_db():
    """Mock database dependency"""
    with patch('core.database.get_db'):
        yield


class TestMigrationRoutes:
    
    def test_initiate_migration_success(self, client: TestClient, mock_auth, mock_db):
        """Test successful migration initiation"""
        
        with patch('modules.pos_migration.services.MigrationOrchestrator') as mock_orchestrator:
            mock_instance = mock_orchestrator.return_value
            mock_instance.initiate_migration = AsyncMock(return_value="migration-123")
            
            response = client.post(
                "/api/v1/pos-migration/initiate",
                json={
                    "pos_config": {
                        "pos_type": "square",
                        "credentials": {
                            "access_token": "test-token",
                            "location_id": "test-location"
                        }
                    },
                    "options": {
                        "import_historical_data": True,
                        "historical_days": 30,
                        "validate_pricing": True,
                        "use_ai_assistance": True
                    }
                },
                headers={"Authorization": "Bearer test-token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["migration_id"] == "migration-123"
            assert data["status"] == "initiated"
            assert "websocket_url" in data
    
    def test_initiate_migration_insufficient_permissions(self, client: TestClient, mock_auth, mock_db):
        """Test migration initiation with insufficient permissions"""
        
        # Change user role
        mock_auth.return_value.role = "staff"
        
        response = client.post(
            "/api/v1/pos-migration/initiate",
            json={
                "pos_config": {
                    "pos_type": "square",
                    "credentials": {"access_token": "test"}
                },
                "options": {}
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]
    
    def test_get_migration_status(self, client: TestClient, mock_auth, mock_db):
        """Test getting migration status"""
        
        mock_status = MigrationStatus(
            migration_id="test-123",
            phase=MigrationPhase.IMPORT,
            progress_percent=65.0,
            items_processed=130,
            total_items=200,
            started_at="2024-01-01T00:00:00"
        )
        
        with patch('modules.pos_migration.services.MigrationOrchestrator') as mock_orchestrator:
            mock_instance = mock_orchestrator.return_value
            mock_instance.get_migration_status = AsyncMock(return_value=mock_status)
            
            response = client.get(
                "/api/v1/pos-migration/test-123/status",
                headers={"Authorization": "Bearer test-token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["migration_id"] == "test-123"
            assert data["phase"] == "import"
            assert data["progress_percent"] == 65.0
    
    def test_approve_field_mappings(self, client: TestClient, mock_auth, mock_db):
        """Test approving field mappings"""
        
        with patch('modules.pos_migration.services.MigrationOrchestrator') as mock_orchestrator:
            mock_instance = mock_orchestrator.return_value
            mock_instance.approve_migration_mappings = AsyncMock()
            
            response = client.post(
                "/api/v1/pos-migration/test-123/approve-mappings",
                json=[
                    {
                        "source_field": "name",
                        "target_field": "name",
                        "confidence": 0.95,
                        "transformation": "none"
                    },
                    {
                        "source_field": "price",
                        "target_field": "price",
                        "confidence": 0.9,
                        "transformation": "parse_decimal"
                    }
                ],
                headers={"Authorization": "Bearer test-token"}
            )
            
            assert response.status_code == 200
            assert response.json()["status"] == "approved"
    
    def test_cancel_migration(self, client: TestClient, mock_auth, mock_db):
        """Test cancelling a migration"""
        
        with patch('modules.pos_migration.services.MigrationOrchestrator') as mock_orchestrator:
            mock_instance = mock_orchestrator.return_value
            mock_instance.cancel_migration = AsyncMock()
            
            response = client.post(
                "/api/v1/pos-migration/test-123/cancel?reason=User%20requested",
                headers={"Authorization": "Bearer test-token"}
            )
            
            assert response.status_code == 200
            assert response.json()["status"] == "cancelled"
    
    def test_suggest_field_mappings(self, client: TestClient, mock_auth, mock_db):
        """Test AI field mapping suggestions"""
        
        mock_suggestions = [
            MappingSuggestion(
                source="itemName",
                target="name",
                confidence=0.95,
                reasoning="Common naming pattern"
            ),
            MappingSuggestion(
                source="itemPrice",
                target="price",
                confidence=0.9,
                reasoning="Price field mapping"
            )
        ]
        
        with patch('modules.pos_migration.agents.MigrationCoachAgent') as mock_agent:
            mock_instance = mock_agent.return_value
            mock_instance.suggest_field_mappings = AsyncMock(return_value=mock_suggestions)
            
            response = client.post(
                "/api/v1/pos-migration/field-mappings/suggest",
                json={
                    "source_fields": ["itemName", "itemPrice", "categoryName"],
                    "target_fields": ["name", "price", "category_id"],
                    "pos_type": "square"
                },
                headers={"Authorization": "Bearer test-token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["source"] == "itemName"
            assert data[0]["target"] == "name"
    
    def test_validate_sample_data(self, client: TestClient, mock_auth, mock_db):
        """Test sample data validation"""
        
        mock_report = ValidationReport(
            anomalies=[],
            summary={
                "total_issues": 0,
                "requires_manual_review": False,
                "confidence": 0.95
            }
        )
        
        with patch('modules.pos_migration.agents.MigrationCoachAgent') as mock_agent:
            mock_instance = mock_agent.return_value
            mock_instance.validate_pricing_data = AsyncMock(return_value=mock_report)
            
            response = client.post(
                "/api/v1/pos-migration/validate-sample-data",
                json={
                    "sample_data": {
                        "menu_items": [
                            {"id": "1", "name": "Test", "price": 999}
                        ]
                    },
                    "pos_type": "square"
                },
                headers={"Authorization": "Bearer test-token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["valid"] is True
            assert data["report"]["summary"]["total_issues"] == 0
    
    def test_test_connection_success(self, client: TestClient, mock_auth, mock_db):
        """Test POS connection testing"""
        
        with patch('modules.pos.adapters.adapter_factory.AdapterFactory.create_adapter') as mock_factory:
            mock_adapter = AsyncMock()
            mock_adapter.test_connection = AsyncMock(return_value=True)
            mock_adapter.fetch_menu_items = AsyncMock(return_value=[
                {"id": "1", "name": "Sample Item", "price": 1000}
            ])
            mock_factory.return_value = mock_adapter
            
            response = client.post(
                "/api/v1/pos-migration/test-connection",
                json={
                    "pos_type": "square",
                    "credentials": {
                        "access_token": "test-token",
                        "location_id": "test-loc"
                    }
                },
                headers={"Authorization": "Bearer test-token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["connected"] is True
            assert data["sample_item_count"] == 1
            assert data["sample_data"]["name"] == "Sample Item"
    
    def test_get_supported_pos_types(self, client: TestClient, mock_auth, mock_db):
        """Test getting supported POS types"""
        
        response = client.get(
            "/api/v1/pos-migration/supported-pos-types",
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "supported_types" in data
        assert len(data["supported_types"]) == 3
        
        # Check Square is included
        square = next(t for t in data["supported_types"] if t["id"] == "square")
        assert square["name"] == "Square"
        assert "access_token" in square["required_credentials"]
    
    def test_get_audit_trail(self, client: TestClient, mock_auth, mock_db):
        """Test getting audit trail"""
        
        with patch('modules.pos_migration.services.AuditService') as mock_audit:
            mock_instance = mock_audit.return_value
            mock_instance.get_audit_trail = AsyncMock(return_value=[
                MagicMock(dict=lambda: {
                    "operation": "migration_initiated",
                    "timestamp": "2024-01-01T00:00:00",
                    "user_id": "test-user"
                })
            ])
            
            response = client.get(
                "/api/v1/pos-migration/audit/test-123",
                headers={"Authorization": "Bearer test-token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["migration_id"] == "test-123"
            assert data["total_logs"] == 1
            assert data["logs"][0]["operation"] == "migration_initiated"