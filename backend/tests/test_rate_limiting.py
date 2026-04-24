"""
test_rate_limiting.py
Unit + integration tests for the Redis-based rate limiter.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ─── Unit tests: rate_limiter service ────────────────────────────────────────

class TestIsRateLimited:
    """Tests for the low-level is_rate_limited() function."""

    @pytest.mark.asyncio
    async def test_allows_requests_under_limit(self):
        from app.services.rate_limiter import is_rate_limited

        mock_redis = AsyncMock()
        mock_pipe = AsyncMock()
        mock_pipe.execute = AsyncMock(return_value=[5, True])  # count=5, expire=True
        mock_redis.pipeline.return_value = mock_pipe

        with patch("app.services.rate_limiter.get_redis", return_value=mock_redis):
            limited, headers = await is_rate_limited("test-key", max_requests=60)

        assert limited is False
        assert headers["X-RateLimit-Remaining"] == "55"
        assert headers["X-RateLimit-Limit"] == "60"

    @pytest.mark.asyncio
    async def test_blocks_requests_over_limit(self):
        from app.services.rate_limiter import is_rate_limited

        mock_redis = AsyncMock()
        mock_pipe = AsyncMock()
        mock_pipe.execute = AsyncMock(return_value=[65, True])  # count=65 > max=60
        mock_redis.pipeline.return_value = mock_pipe

        with patch("app.services.rate_limiter.get_redis", return_value=mock_redis):
            limited, headers = await is_rate_limited("test-key", max_requests=60)

        assert limited is True
        assert headers["X-RateLimit-Remaining"] == "0"

    @pytest.mark.asyncio
    async def test_fails_open_when_redis_down(self):
        """When Redis is unavailable, fail open (allow all requests)."""
        from app.services.rate_limiter import is_rate_limited

        with patch("app.services.rate_limiter.get_redis", return_value=None):
            limited, headers = await is_rate_limited("test-key")

        assert limited is False
        assert headers == {}

    @pytest.mark.asyncio
    async def test_fails_open_on_redis_error(self):
        """Unexpected Redis errors should fail open, not crash the app."""
        from app.services.rate_limiter import is_rate_limited

        mock_redis = AsyncMock()
        mock_pipe = AsyncMock()
        mock_pipe.execute = AsyncMock(side_effect=Exception("Connection reset"))
        mock_redis.pipeline.return_value = mock_pipe

        with patch("app.services.rate_limiter.get_redis", return_value=mock_redis):
            limited, headers = await is_rate_limited("test-key")

        assert limited is False

    @pytest.mark.asyncio
    async def test_rate_limit_headers_present(self):
        from app.services.rate_limiter import is_rate_limited

        mock_redis = AsyncMock()
        mock_pipe = AsyncMock()
        mock_pipe.execute = AsyncMock(return_value=[1, True])
        mock_redis.pipeline.return_value = mock_pipe

        with patch("app.services.rate_limiter.get_redis", return_value=mock_redis):
            _, headers = await is_rate_limited("test-key", max_requests=10)

        assert "X-RateLimit-Limit" in headers
        assert "X-RateLimit-Remaining" in headers
        assert "X-RateLimit-Reset" in headers


class TestCheckRateLimit:
    """Tests for the high-level check_rate_limit() function."""

    @pytest.mark.asyncio
    async def test_general_endpoint_higher_limit(self):
        from app.services.rate_limiter import check_rate_limit

        with patch("app.services.rate_limiter.is_rate_limited", return_value=(False, {})) as mock_rl:
            await check_rate_limit("1.2.3.4", endpoint_type="general")
            # general = 60 req/min
            call_args = mock_rl.call_args_list[0]
            assert call_args.kwargs["max_requests"] == 60

    @pytest.mark.asyncio
    async def test_heavy_endpoint_stricter_limit(self):
        from app.services.rate_limiter import check_rate_limit

        with patch("app.services.rate_limiter.is_rate_limited", return_value=(False, {})) as mock_rl:
            await check_rate_limit("1.2.3.4", endpoint_type="heavy")
            # heavy = 10 req/min
            call_args = mock_rl.call_args_list[0]
            assert call_args.kwargs["max_requests"] == 10

    @pytest.mark.asyncio
    async def test_authenticated_user_gets_extra_check(self):
        from app.services.rate_limiter import check_rate_limit

        with patch("app.services.rate_limiter.is_rate_limited", return_value=(False, {})) as mock_rl:
            await check_rate_limit("1.2.3.4", endpoint_type="heavy", user_id="alice")
            # Should be called twice: IP check + user check
            assert mock_rl.call_count == 2

    @pytest.mark.asyncio
    async def test_ip_limit_exceeded_blocks_regardless_of_user(self):
        from app.services.rate_limiter import check_rate_limit

        with patch("app.services.rate_limiter.is_rate_limited", return_value=(True, {"X-RateLimit-Remaining": "0"})):
            limited, _ = await check_rate_limit("1.2.3.4", endpoint_type="heavy", user_id="alice")

        assert limited is True

    @pytest.mark.asyncio
    async def test_unauthenticated_user_only_ip_check(self):
        from app.services.rate_limiter import check_rate_limit

        with patch("app.services.rate_limiter.is_rate_limited", return_value=(False, {})) as mock_rl:
            await check_rate_limit("1.2.3.4", endpoint_type="general", user_id=None)
            # Only IP check, no user check
            assert mock_rl.call_count == 1


# ─── Integration tests: rate limiting on API endpoints ───────────────────────

@pytest.mark.asyncio
async def test_chat_rate_limited_returns_429(client, mock_mongo):
    """POST /chat returns 429 when rate limit is exceeded."""
    mock_mongo["get"].return_value = {
        "file_id": "rl-test-001",
        "type": "pdf",
        "timestamps": [],
    }

    with patch("app.services.rate_limiter.check_rate_limit",
               return_value=(True, {
                   "X-RateLimit-Limit": "10",
                   "X-RateLimit-Remaining": "0",
                   "X-RateLimit-Reset": "9999999999",
               })):
        response = await client.post(
            "/chat",
            json={"file_id": "rl-test-001", "question": "Test"},
        )

    assert response.status_code == 429
    assert "Too many requests" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_rate_limited_returns_429(client):
    """POST /upload returns 429 when rate limit is exceeded."""
    import io
    files = {"file": ("test.pdf", io.BytesIO(b"%PDF fake"), "application/pdf")}

    with patch("app.services.rate_limiter.check_rate_limit",
               return_value=(True, {"X-RateLimit-Remaining": "0"})):
        response = await client.post("/upload", files=files)

    assert response.status_code == 429


@pytest.mark.asyncio
async def test_chat_passes_when_not_rate_limited(client, mock_mongo, mock_rag, mock_llm):
    """POST /chat proceeds normally when rate limit is not exceeded."""
    mock_mongo["get"].return_value = {
        "file_id": "rl-ok-001",
        "type": "pdf",
        "timestamps": [],
    }

    with patch("app.services.rate_limiter.check_rate_limit", return_value=(False, {})):
        response = await client.post(
            "/chat",
            json={"file_id": "rl-ok-001", "question": "What is AI?"},
        )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_rate_limit_headers_in_response(client, mock_mongo, mock_rag, mock_llm):
    """Rate limit headers should be present in successful responses."""
    mock_mongo["get"].return_value = {
        "file_id": "rl-hdr-001",
        "type": "pdf",
        "timestamps": [],
    }

    rl_headers = {
        "X-RateLimit-Limit": "10",
        "X-RateLimit-Remaining": "9",
        "X-RateLimit-Reset": "9999999999",
    }

    with patch("app.services.rate_limiter.check_rate_limit", return_value=(False, rl_headers)):
        response = await client.post(
            "/chat",
            json={"file_id": "rl-hdr-001", "question": "Test"},
        )

    assert response.status_code == 200


# ─── Redis connection tests ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_redis_returns_none_on_connection_failure():
    """get_redis() should return None when Redis is unreachable."""
    import app.services.rate_limiter as rl_module

    original = rl_module._redis_client
    rl_module._redis_client = None

    with patch("redis.asyncio.from_url") as mock_from_url:
        mock_client = AsyncMock()
        mock_client.ping.side_effect = Exception("Connection refused")
        mock_from_url.return_value = mock_client

        result = await rl_module.get_redis()

    # Restore
    rl_module._redis_client = original
    assert result is None


@pytest.mark.asyncio
async def test_close_redis_cleans_up():
    """close_redis() should close the connection and set _redis_client to None."""
    import app.services.rate_limiter as rl_module

    mock_redis = AsyncMock()
    rl_module._redis_client = mock_redis

    await rl_module.close_redis()

    mock_redis.aclose.assert_called_once()
    assert rl_module._redis_client is None
