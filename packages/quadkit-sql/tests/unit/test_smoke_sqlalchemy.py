from sqlalchemy import create_engine, text


def test_create_in_memory_engine():
    engine = create_engine("sqlite:///:memory:")
    assert engine is not None

    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        # SQLAlchemy 2.x: use scalar() to get scalar
        assert result.scalar() == 1
