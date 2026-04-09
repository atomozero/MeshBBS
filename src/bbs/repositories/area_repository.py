"""
Area repository for data access operations.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from typing import Optional, List

from sqlalchemy.orm import Session

from .base_repository import BaseRepository
from bbs.models.area import Area
from bbs.models.activity_log import ActivityLog, EventType


class AreaRepository(BaseRepository[Area]):
    """Repository for Area entity operations."""

    model = Area

    def __init__(self, session: Session):
        super().__init__(session)

    def get_by_name(self, name: str) -> Optional[Area]:
        """
        Get area by name (case-insensitive).

        Args:
            name: Area name

        Returns:
            Area or None if not found
        """
        return (
            self.session.query(Area)
            .filter(Area.name.ilike(name))
            .first()
        )

    def get_public_areas(self) -> List[Area]:
        """
        Get all public areas.

        Returns:
            List of public areas
        """
        return (
            self.session.query(Area)
            .filter(Area.is_public == True)
            .order_by(Area.name)
            .all()
        )

    def get_writable_areas(self) -> List[Area]:
        """
        Get all areas that allow posting.

        Returns:
            List of writable areas
        """
        return (
            self.session.query(Area)
            .filter(Area.is_public == True)
            .filter(Area.is_readonly == False)
            .order_by(Area.name)
            .all()
        )

    def create_area(
        self,
        name: str,
        description: Optional[str] = None,
        is_public: bool = True,
        is_readonly: bool = False,
        created_by: Optional[str] = None,
    ) -> Area:
        """
        Create a new area.

        Args:
            name: Area name
            description: Area description
            is_public: Whether area is public
            is_readonly: Whether area is read-only
            created_by: Public key of creator

        Returns:
            Created area
        """
        area = Area(
            name=name.lower(),
            description=description,
            is_public=is_public,
            is_readonly=is_readonly,
        )
        self.session.add(area)

        # Log creation
        self.session.add(
            ActivityLog.log(
                EventType.AREA_CREATED,
                user_key=created_by,
                details=f"Created area: {name}",
            )
        )

        return area

    def delete_area(self, name: str, deleted_by: Optional[str] = None) -> bool:
        """
        Delete an area.

        Args:
            name: Area name
            deleted_by: Public key of deleter

        Returns:
            True if deleted, False if not found
        """
        area = self.get_by_name(name)
        if not area:
            return False

        area_name = area.name
        self.session.delete(area)

        # Log deletion
        self.session.add(
            ActivityLog.log(
                EventType.AREA_DELETED,
                user_key=deleted_by,
                details=f"Deleted area: {area_name}",
            )
        )

        return True

    def update_area(
        self,
        name: str,
        new_description: Optional[str] = None,
        new_readonly: Optional[bool] = None,
        new_public: Optional[bool] = None,
        modified_by: Optional[str] = None,
    ) -> Optional[Area]:
        """
        Update an area's properties.

        Args:
            name: Area name
            new_description: New description (None to keep current)
            new_readonly: New readonly status (None to keep current)
            new_public: New public status (None to keep current)
            modified_by: Public key of modifier

        Returns:
            Updated area or None if not found
        """
        area = self.get_by_name(name)
        if not area:
            return None

        changes = []

        if new_description is not None and new_description != area.description:
            area.description = new_description
            changes.append("description")

        if new_readonly is not None and new_readonly != area.is_readonly:
            area.is_readonly = new_readonly
            changes.append(f"readonly={new_readonly}")

        if new_public is not None and new_public != area.is_public:
            area.is_public = new_public
            changes.append(f"public={new_public}")

        if changes:
            self.session.add(
                ActivityLog.log(
                    EventType.AREA_MODIFIED,
                    user_key=modified_by,
                    details=f"Modified area {name}: {', '.join(changes)}",
                )
            )

        return area

    def get_all_areas(self) -> List[Area]:
        """
        Get all areas (including non-public).

        Returns:
            List of all areas
        """
        return (
            self.session.query(Area)
            .order_by(Area.name)
            .all()
        )

    def get_area_stats(self) -> List[dict]:
        """
        Get statistics for all areas.

        Returns:
            List of dicts with area stats
        """
        areas = self.get_public_areas()
        return [
            {
                "name": area.name,
                "description": area.description,
                "message_count": area.message_count,
                "last_post": area.last_post_at,
            }
            for area in areas
        ]
