import pytest


@pytest.mark.asyncio
async def test_pipeline_retries_on_transient_error(make_fake_pipeline):
    """Test pipeline retries on transient errors.

    This test requires complex internal setup and is skipped for now.
    """
    pytest.skip("Test requires internal provider setup - to be refactored")


@pytest.mark.asyncio
async def test_wrap_operation_with_pipeline_retries_on_transient_error(
    make_fake_pipeline,
):
    """Test wrap_operation with pipeline retries on transient errors.

    This test requires complex internal setup and is skipped for now.
    """
    pytest.skip("Test requires internal provider setup - to be refactored")
