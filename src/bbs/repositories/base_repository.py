"""
Base repository class with common operations.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from typing import TypeVar, Generic, Optional, List, Type
from sqlalchemy.orm import Session

from bbs.models.base import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """
    Base repository providing common CRUD operations.

    Subclass this for specific entity repositories.
    """

    model: Type[T]

    def __init__(self, session: Session):
        """
        Initialize repository with a database session.

        Args:
            session: SQLAlchemy session
        """
        self.session = session

    def get_by_id(self, id: int) -> Optional[T]:
        """
        Get entity by primary key.

        Args:
            id: Primary key value

        Returns:
            Entity or None if not found
        """
        return self.session.query(self.model).get(id)

    def get_all(self) -> List[T]:
        """
        Get all entities.

        Returns:
            List of all entities
        """
        return self.session.query(self.model).all()

    def add(self, entity: T) -> T:
        """
        Add a new entity to the session.

        Args:
            entity: Entity to add

        Returns:
            The added entity
        """
        self.session.add(entity)
        return entity

    def delete(self, entity: T) -> None:
        """
        Delete an entity.

        Args:
            entity: Entity to delete
        """
        self.session.delete(entity)

    def count(self) -> int:
        """
        Count all entities.

        Returns:
            Total count
        """
        return self.session.query(self.model).count()
