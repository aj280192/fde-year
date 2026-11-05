from sqlalchemy import Engine, create_engine


def make_engine(db_url: str) -> Engine:
    """Create a SQLAlchemy engine for the given database URL."""
    return create_engine(db_url, pool_pre_ping=True)
