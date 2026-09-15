"""Unit tests for transport domain"""
import pytest

from quadkit import serialization as json
from quadkit.web import (
    FastJSONResponse,
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)


class TestJSONResponse:
    """Test JSON response functionality"""

    def test_json_response_creation(self):
        """Test JSON response creation"""
        data = {"message": "success", "data": [1, 2, 3]}
        response = JSONResponse(data)

        assert response.status_code == 200
        assert response.media_type == "application/json"
        assert json.loads(response.body.decode()) == data

    def test_json_response_custom_status(self):
        """Test JSON response with custom status code"""
        data = {"error": "not found"}
        response = JSONResponse(data, status_code=404)

        assert response.status_code == 404
        assert json.loads(response.body.decode()) == data

    def test_json_response_with_headers(self):
        """Test JSON response with custom headers"""
        data = {"result": "ok"}
        headers = {"x-custom": "value"}
        response = JSONResponse(data, headers=headers)

        assert response.status_code == 200
        assert response.headers["x-custom"] == "value"
        assert json.loads(response.body.decode()) == data


class TestHTMLResponse:
    """Test HTML response functionality"""

    def test_html_response_creation(self):
        """Test HTML response creation"""
        html_content = "<html><body><h1>Hello</h1></body></html>"
        response = HTMLResponse(html_content)

        assert response.status_code == 200
        assert response.media_type == "text/html"
        assert response.body.decode() == html_content

    def test_html_response_custom_status(self):
        """Test HTML response with custom status"""
        html_content = "<html><body><h1>Error</h1></body></html>"
        response = HTMLResponse(html_content, status_code=500)

        assert response.status_code == 500
        assert response.media_type == "text/html"


class TestFileResponse:
    """Test file response functionality"""

    def test_file_response_creation(self):
        """Test file response creation"""
        response = FileResponse("/path/to/file.txt")

        assert response.status_code == 200
        assert "text/plain" in response.media_type

    def test_file_response_with_mime_type(self):
        """Test file response with explicit MIME type"""
        response = FileResponse("/path/to/image.png", media_type="image/png")

        assert response.media_type == "image/png"


class TestRedirectResponse:
    """Test redirect response functionality"""

    def test_redirect_response_creation(self):
        """Test redirect response creation"""
        response = RedirectResponse("/new-location")

        assert response.status_code == 307
        assert response.headers["location"] == "/new-location"

    def test_redirect_response_permanent(self):
        """Test permanent redirect"""
        response = RedirectResponse("/new-location", status_code=301)

        assert response.status_code == 301
        assert response.headers["location"] == "/new-location"


class TestStreamingResponse:
    """Test streaming response functionality"""

    @pytest.mark.asyncio
    async def test_streaming_response_creation(self):
        """Test streaming response creation"""

        async def content_generator():
            yield b"chunk1"
            yield b"chunk2"
            yield b"chunk3"

        response = StreamingResponse(content_generator(), media_type="text/plain")

        assert response.status_code == 200
        assert response.media_type == "text/plain"

    @pytest.mark.asyncio
    async def test_streaming_response_json(self):
        """Test streaming JSON response"""

        async def json_generator():
            yield b'{"item": 1}'
            yield b'{"item": 2}'

        response = StreamingResponse(json_generator(), media_type="application/json")

        assert response.media_type == "application/json"


class TestResponseBase:
    """Test base response functionality"""

    def test_response_creation(self):
        """Test basic response creation"""
        response = Response(
            content="Hello World",
            status_code=200,
            headers={"custom": "header"},
            media_type="text/plain",
        )

        assert response.status_code == 200
        assert response.body == b"Hello World"
        assert response.headers["custom"] == "header"
        assert response.media_type == "text/plain"

    def test_response_default_content_type(self):
        """Test response default content type"""
        response = Response(content="test", media_type="text/plain")

        assert response.media_type == "text/plain"


class TestFastJSONResponse:
    """Test fast JSON response"""

    def test_fast_json_response_creation(self):
        """Test fast JSON response creation"""
        data = {"fast": True, "data": [1, 2, 3, 4, 5]}
        response = FastJSONResponse(data)

        assert response.status_code == 200
        assert response.media_type == "application/json"

        # Should be valid JSON
        parsed = json.loads(response.body.decode())
        assert parsed == data

    def test_fast_json_response_performance(self):
        """Test that fast JSON is actually faster (basic check)"""
        import time

        data = {"items": list(range(1000))}

        # Fast JSON response
        start = time.time()
        fast_response = FastJSONResponse(data)
        fast_time = time.time() - start

        # Regular JSON response
        start = time.time()
        regular_response = JSONResponse(data)
        regular_time = time.time() - start

        # Fast should be at least as fast (may be same in simple cases)
        assert fast_time <= regular_time + 0.01  # Allow small variance
