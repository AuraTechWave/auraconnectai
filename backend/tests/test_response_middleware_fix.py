"""
Tests to verify the response middleware fix

Ensures the middleware properly wraps responses and doesn't return early.
"""

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse, PlainTextResponse
from fastapi.testclient import TestClient
from typing import List
import json
import io

from core.response_middleware import ResponseStandardizationMiddleware
from core.response_models import StandardResponse


# Create test app with middleware
app = FastAPI()
app.add_middleware(
    ResponseStandardizationMiddleware,
    exclude_paths=["/health"]
)


@app.get("/test/dict")
async def return_dict():
    """Returns a plain dict - should be wrapped"""
    return {"message": "Hello", "value": 123}


@app.get("/test/list")
async def return_list():
    """Returns a list - should be wrapped"""
    return [{"id": 1}, {"id": 2}, {"id": 3}]


@app.get("/test/json-response")
async def return_json_response():
    """Returns JSONResponse - should be wrapped"""
    return JSONResponse(content={"data": "test"})


@app.get("/test/standard-response")
async def return_standard_response():
    """Returns StandardResponse - should pass through with updated meta"""
    return StandardResponse.success(data={"id": 1}, message="Already standard")


@app.get("/test/streaming")
async def return_streaming():
    """Returns StreamingResponse - should NOT be wrapped"""
    def generate():
        yield b"chunk1"
        yield b"chunk2"
        yield b"chunk3"
    
    return StreamingResponse(generate(), media_type="text/plain")


@app.get("/test/file")
async def return_file():
    """Returns FileResponse - should NOT be wrapped"""
    # Create a temporary file-like object
    content = b"File content here"
    return FileResponse(
        path="/dev/null",  # Using /dev/null as a dummy path
        media_type="application/octet-stream",
        headers={"Content-Length": str(len(content))}
    )


@app.get("/test/plain-text")
async def return_plain_text():
    """Returns PlainTextResponse - should be wrapped"""
    return PlainTextResponse(content="Plain text content")


@app.get("/test/error")
async def return_error():
    """Raises HTTPException - should be wrapped as error"""
    raise HTTPException(status_code=404, detail="Not found")


@app.get("/test/exception")
async def return_exception():
    """Raises generic exception - should be wrapped as error"""
    raise ValueError("Something went wrong")


@app.get("/health")
async def health_check():
    """Health endpoint - should be excluded from wrapping"""
    return {"status": "healthy"}


client = TestClient(app)


class TestMiddlewareFix:
    """Test that the middleware properly wraps responses"""
    
    def test_dict_response_wrapped(self):
        """Test that dict responses are wrapped"""
        response = client.get("/test/dict")
        assert response.status_code == 200
        
        data = response.json()
        assert "success" in data
        assert data["success"] is True
        assert "data" in data
        assert data["data"] == {"message": "Hello", "value": 123}
        assert "meta" in data
        assert "request_id" in data["meta"]
        assert "processing_time_ms" in data["meta"]
    
    def test_list_response_wrapped(self):
        """Test that list responses are wrapped"""
        response = client.get("/test/list")
        assert response.status_code == 200
        
        data = response.json()
        assert "success" in data
        assert data["success"] is True
        assert "data" in data
        assert isinstance(data["data"], list)
        assert len(data["data"]) == 3
        assert "meta" in data
    
    def test_json_response_wrapped(self):
        """Test that JSONResponse is wrapped"""
        response = client.get("/test/json-response")
        assert response.status_code == 200
        
        data = response.json()
        assert "success" in data
        assert data["success"] is True
        assert "data" in data
        assert data["data"] == {"data": "test"}
        assert "meta" in data
    
    def test_standard_response_passthrough(self):
        """Test that StandardResponse passes through with updated meta"""
        response = client.get("/test/standard-response")
        assert response.status_code == 200
        
        data = response.json()
        assert "success" in data
        assert data["success"] is True
        assert data["data"] == {"id": 1}
        assert data["message"] == "Already standard"
        assert "meta" in data
        assert "request_id" in data["meta"]
        assert "processing_time_ms" in data["meta"]
    
    def test_streaming_response_not_wrapped(self):
        """Test that StreamingResponse is NOT wrapped"""
        response = client.get("/test/streaming")
        assert response.status_code == 200
        
        # Should get raw streaming content, not JSON
        content = response.content
        assert content == b"chunk1chunk2chunk3"
        
        # Should have request ID header but body is not wrapped
        assert "x-request-id" in response.headers
    
    def test_file_response_not_wrapped(self):
        """Test that FileResponse is NOT wrapped"""
        response = client.get("/test/file")
        # FileResponse with /dev/null might fail, but should not be JSON wrapped
        
        try:
            # If we can parse as JSON, it was incorrectly wrapped
            data = response.json()
            pytest.fail("FileResponse should not be wrapped in JSON")
        except json.JSONDecodeError:
            # This is expected - file responses should not be JSON
            pass
    
    def test_plain_text_wrapped(self):
        """Test that PlainTextResponse is wrapped"""
        response = client.get("/test/plain-text")
        assert response.status_code == 200
        
        data = response.json()
        assert "success" in data
        assert data["success"] is True
        assert "data" in data
        assert data["data"] == "Plain text content"
        assert "meta" in data
    
    def test_http_exception_wrapped(self):
        """Test that HTTPException is wrapped as error"""
        response = client.get("/test/error")
        assert response.status_code == 404
        
        data = response.json()
        assert "success" in data
        assert data["success"] is False
        assert data["data"] is None
        assert "errors" in data
        assert len(data["errors"]) > 0
        assert data["errors"][0]["code"] == "NOT_FOUND"
        assert "meta" in data
    
    def test_generic_exception_wrapped(self):
        """Test that generic exceptions are wrapped as error"""
        response = client.get("/test/exception")
        assert response.status_code == 500
        
        data = response.json()
        assert "success" in data
        assert data["success"] is False
        assert "errors" in data
        assert "meta" in data
    
    def test_excluded_path_not_wrapped(self):
        """Test that excluded paths are not wrapped"""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        # Should get raw response, not wrapped
        assert data == {"status": "healthy"}
        assert "success" not in data
        assert "meta" not in data
    
    def test_request_id_header_propagated(self):
        """Test that custom request ID is used when provided"""
        custom_id = "custom-request-123"
        response = client.get("/test/dict", headers={"X-Request-ID": custom_id})
        assert response.status_code == 200
        
        data = response.json()
        assert data["meta"]["request_id"] == custom_id
    
    def test_processing_time_measured(self):
        """Test that processing time is measured"""
        response = client.get("/test/dict")
        assert response.status_code == 200
        
        data = response.json()
        assert "processing_time_ms" in data["meta"]
        assert isinstance(data["meta"]["processing_time_ms"], (int, float))
        assert data["meta"]["processing_time_ms"] >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])