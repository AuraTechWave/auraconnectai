"""
Tests for JSON handling efficiency in response middleware

Verifies that the middleware doesn't do unnecessary JSON serialization/deserialization.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict

from core.response_middleware import ResponseStandardizationMiddleware
from core.response_models import StandardResponse


app = FastAPI()
app.add_middleware(ResponseStandardizationMiddleware)


@app.get("/test/datetime")
async def return_datetime():
    """Returns response with datetime - should be serialized correctly"""
    return {
        "timestamp": datetime.now(),
        "date": date.today(),
        "message": "Datetime test"
    }


@app.get("/test/decimal")
async def return_decimal():
    """Returns response with Decimal - should be serialized correctly"""
    return {
        "price": Decimal("99.99"),
        "tax": Decimal("8.25"),
        "total": Decimal("108.24")
    }


@app.get("/test/nested")
async def return_nested():
    """Returns deeply nested response"""
    return {
        "level1": {
            "level2": {
                "level3": {
                    "timestamp": datetime.now(),
                    "value": Decimal("123.45")
                }
            }
        }
    }


@app.get("/test/standard-with-datetime")
async def return_standard_with_datetime():
    """Returns StandardResponse with datetime in data"""
    data = {
        "id": 1,
        "created_at": datetime.now(),
        "amount": Decimal("999.99")
    }
    return StandardResponse.success(data=data, message="Success")


@app.get("/test/already-standard")
async def return_already_standard():
    """Returns a response that's already in standard format"""
    # Simulate a response that's already standardized
    return JSONResponse(content={
        "success": True,
        "data": {"id": 1},
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "version": "1.0"
        },
        "errors": [],
        "message": "Already standardized"
    })


@app.get("/test/malformed-meta")
async def return_malformed_meta():
    """Returns a response with non-dict meta field"""
    return JSONResponse(content={
        "success": True,
        "data": {"id": 1},
        "meta": "invalid_meta_string",  # This should not cause TypeError
        "errors": []
    })


client = TestClient(app)


class TestJSONEfficiency:
    """Test efficient JSON handling in middleware"""
    
    def test_datetime_serialization(self):
        """Test that datetime objects are serialized correctly"""
        response = client.get("/test/datetime")
        assert response.status_code == 200
        
        data = response.json()
        assert "success" in data
        assert data["success"] is True
        assert "timestamp" in data["data"]
        assert "date" in data["data"]
        # Should be serialized as strings
        assert isinstance(data["data"]["timestamp"], str)
        assert isinstance(data["data"]["date"], str)
    
    def test_decimal_serialization(self):
        """Test that Decimal objects are serialized correctly"""
        response = client.get("/test/decimal")
        assert response.status_code == 200
        
        data = response.json()
        assert "success" in data
        assert data["success"] is True
        assert data["data"]["price"] == 99.99
        assert data["data"]["tax"] == 8.25
        assert data["data"]["total"] == 108.24
    
    def test_nested_serialization(self):
        """Test that deeply nested objects are serialized correctly"""
        response = client.get("/test/nested")
        assert response.status_code == 200
        
        data = response.json()
        assert "success" in data
        assert data["success"] is True
        assert "level1" in data["data"]
        assert "level2" in data["data"]["level1"]
        assert "level3" in data["data"]["level1"]["level2"]
        
        level3 = data["data"]["level1"]["level2"]["level3"]
        assert isinstance(level3["timestamp"], str)
        assert level3["value"] == 123.45
    
    def test_standard_response_with_datetime(self):
        """Test StandardResponse with datetime in data"""
        response = client.get("/test/standard-with-datetime")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Success"
        assert isinstance(data["data"]["created_at"], str)
        assert data["data"]["amount"] == 999.99
    
    def test_already_standard_efficiency(self):
        """Test that already-standard responses are handled efficiently"""
        response = client.get("/test/already-standard")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Already standardized"
        # Meta should be updated with request_id and processing_time_ms
        assert "request_id" in data["meta"]
        assert "processing_time_ms" in data["meta"]
        assert data["meta"]["version"] == "1.0"
    
    def test_malformed_meta_handling(self):
        """Test that malformed meta doesn't cause TypeError"""
        response = client.get("/test/malformed-meta")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        # Meta should remain unchanged if it's not a dict
        assert data["meta"] == "invalid_meta_string"
    
    def test_no_double_serialization(self):
        """Verify that we're not doing unnecessary JSON operations"""
        # This test checks that the response is valid JSON
        # If we were doing json.loads(json.dumps(...)) incorrectly,
        # we might get malformed JSON or errors
        
        response = client.get("/test/datetime")
        assert response.status_code == 200
        
        # Should be able to parse JSON directly
        import json
        data = json.loads(response.text)
        assert data["success"] is True
        
        # Check that special characters are not double-escaped
        response = client.get("/test/nested")
        text = response.text
        # Should not contain double-escaped quotes
        assert '\\\\"' not in text
        assert '\\\\n' not in text


class TestPerformance:
    """Test performance implications of JSON handling"""
    
    def test_large_response_efficiency(self):
        """Test that large responses are handled efficiently"""
        
        @app.get("/test/large")
        async def return_large():
            # Create a large response
            return {
                "items": [
                    {
                        "id": i,
                        "name": f"Item {i}",
                        "timestamp": datetime.now(),
                        "price": Decimal(str(i * 10.99))
                    }
                    for i in range(1000)
                ]
            }
        
        response = client.get("/test/large")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["data"]["items"]) == 1000
        # All timestamps should be serialized
        for item in data["data"]["items"]:
            assert isinstance(item["timestamp"], str)
            assert isinstance(item["price"], (int, float))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])