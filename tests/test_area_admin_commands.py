"""
Tests for area administration commands (newarea, delarea, editarea, listareas).

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import pytest
from sqlalchemy.orm import Session

from bbs.commands.dispatcher import CommandDispatcher
from bbs.models.user import User
from bbs.models.area import Area


class TestNewAreaCommand:
    """Tests for /newarea command."""

    @pytest.mark.asyncio
    async def test_newarea_no_args(self, db_session: Session, admin_sender_key: str):
        """Test /newarea without arguments shows usage."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/newarea", admin_sender_key)

        assert response is not None
        assert "uso" in response.lower()

    @pytest.mark.asyncio
    async def test_newarea_non_admin_denied(
        self, db_session: Session, test_sender_key: str
    ):
        """Test non-admin cannot use /newarea."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/newarea test", test_sender_key)

        assert response is not None
        assert "permesso negato" in response.lower()

    @pytest.mark.asyncio
    async def test_newarea_success(
        self, db_session: Session, admin_sender_key: str
    ):
        """Test successful area creation."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/newarea gaming", admin_sender_key)

        assert response is not None
        assert "creata" in response.lower()
        assert "gaming" in response.lower()

        # Verify area was created
        area = db_session.query(Area).filter_by(name="gaming").first()
        assert area is not None

    @pytest.mark.asyncio
    async def test_newarea_with_description(
        self, db_session: Session, admin_sender_key: str
    ):
        """Test area creation with description."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(
            "/newarea music Discussioni musicali", admin_sender_key
        )

        assert response is not None
        assert "creata" in response.lower()
        assert "discussioni musicali" in response.lower()

        area = db_session.query(Area).filter_by(name="music").first()
        assert area is not None
        assert area.description == "Discussioni musicali"

    @pytest.mark.asyncio
    async def test_newarea_with_hash_prefix(
        self, db_session: Session, admin_sender_key: str
    ):
        """Test area creation with # prefix (should be stripped)."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/newarea #sports", admin_sender_key)

        assert response is not None
        assert "creata" in response.lower()

        area = db_session.query(Area).filter_by(name="sports").first()
        assert area is not None

    @pytest.mark.asyncio
    async def test_newarea_already_exists(
        self, db_session: Session, admin_sender_key: str, sample_areas: list[Area]
    ):
        """Test creating area that already exists."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/newarea generale", admin_sender_key)

        assert response is not None
        assert "esiste già" in response.lower()

    @pytest.mark.asyncio
    async def test_newarea_name_too_short(
        self, db_session: Session, admin_sender_key: str
    ):
        """Test area name too short."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/newarea a", admin_sender_key)

        assert response is not None
        assert "troppo corto" in response.lower()

    @pytest.mark.asyncio
    async def test_newarea_name_too_long(
        self, db_session: Session, admin_sender_key: str
    ):
        """Test area name too long."""
        long_name = "a" * 50
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(f"/newarea {long_name}", admin_sender_key)

        assert response is not None
        assert "troppo lungo" in response.lower()

    @pytest.mark.asyncio
    async def test_newarea_invalid_name_format(
        self, db_session: Session, admin_sender_key: str
    ):
        """Test area name with invalid characters."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/newarea test@area", admin_sender_key)

        assert response is not None
        assert "non valido" in response.lower()

    @pytest.mark.asyncio
    async def test_newarea_name_starts_with_number(
        self, db_session: Session, admin_sender_key: str
    ):
        """Test area name starting with number (invalid)."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/newarea 123test", admin_sender_key)

        assert response is not None
        assert "non valido" in response.lower()

    @pytest.mark.asyncio
    async def test_newarea_valid_name_with_underscore(
        self, db_session: Session, admin_sender_key: str
    ):
        """Test area name with underscore (valid)."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/newarea off_topic", admin_sender_key)

        assert response is not None
        assert "creata" in response.lower()

    @pytest.mark.asyncio
    async def test_newarea_valid_name_with_hyphen(
        self, db_session: Session, admin_sender_key: str
    ):
        """Test area name with hyphen (valid)."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/newarea off-topic", admin_sender_key)

        assert response is not None
        assert "creata" in response.lower()

    @pytest.mark.asyncio
    async def test_newarea_alias_createarea(
        self, db_session: Session, admin_sender_key: str
    ):
        """Test /createarea alias."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/createarea alias_test", admin_sender_key)

        assert response is not None
        assert "creata" in response.lower()


class TestDelAreaCommand:
    """Tests for /delarea command."""

    @pytest.mark.asyncio
    async def test_delarea_no_args(self, db_session: Session, admin_sender_key: str):
        """Test /delarea without arguments shows usage."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/delarea", admin_sender_key)

        assert response is not None
        assert "uso" in response.lower()

    @pytest.mark.asyncio
    async def test_delarea_non_admin_denied(
        self, db_session: Session, test_sender_key: str
    ):
        """Test non-admin cannot use /delarea."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/delarea test", test_sender_key)

        assert response is not None
        assert "permesso negato" in response.lower()

    @pytest.mark.asyncio
    async def test_delarea_success(
        self, db_session: Session, admin_sender_key: str
    ):
        """Test successful area deletion."""
        # Create area first
        area = Area(name="todelete", description="Test area")
        db_session.add(area)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/delarea todelete", admin_sender_key)

        assert response is not None
        assert "eliminata" in response.lower()

        # Verify area was deleted
        area = db_session.query(Area).filter_by(name="todelete").first()
        assert area is None

    @pytest.mark.asyncio
    async def test_delarea_not_found(
        self, db_session: Session, admin_sender_key: str
    ):
        """Test deleting non-existent area."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/delarea nonexistent", admin_sender_key)

        assert response is not None
        assert "non trovata" in response.lower()

    @pytest.mark.asyncio
    async def test_delarea_protected(
        self, db_session: Session, admin_sender_key: str, sample_areas: list[Area]
    ):
        """Test cannot delete protected area (generale)."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/delarea generale", admin_sender_key)

        assert response is not None
        assert "protetta" in response.lower()

    @pytest.mark.asyncio
    async def test_delarea_shows_message_count(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test deletion shows message count."""
        # Create area with messages
        area = Area(name="withmessages", message_count=5)
        db_session.add(area)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/delarea withmessages", admin_sender_key)

        assert response is not None
        assert "eliminata" in response.lower()
        assert "5 messaggi" in response.lower()

    @pytest.mark.asyncio
    async def test_delarea_with_hash_prefix(
        self, db_session: Session, admin_sender_key: str
    ):
        """Test deletion with # prefix."""
        area = Area(name="hashtest")
        db_session.add(area)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/delarea #hashtest", admin_sender_key)

        assert response is not None
        assert "eliminata" in response.lower()


class TestEditAreaCommand:
    """Tests for /editarea command."""

    @pytest.mark.asyncio
    async def test_editarea_no_args(self, db_session: Session, admin_sender_key: str):
        """Test /editarea without arguments shows usage."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/editarea", admin_sender_key)

        assert response is not None
        assert "uso" in response.lower()

    @pytest.mark.asyncio
    async def test_editarea_non_admin_denied(
        self, db_session: Session, test_sender_key: str
    ):
        """Test non-admin cannot use /editarea."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/editarea test desc Test", test_sender_key)

        assert response is not None
        assert "permesso negato" in response.lower()

    @pytest.mark.asyncio
    async def test_editarea_change_description(
        self, db_session: Session, admin_sender_key: str, sample_areas: list[Area]
    ):
        """Test changing area description."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(
            "/editarea tech desc Area per discussioni tecniche", admin_sender_key
        )

        assert response is not None
        assert "aggiornata" in response.lower()

        area = db_session.query(Area).filter_by(name="tech").first()
        assert area.description == "Area per discussioni tecniche"

    @pytest.mark.asyncio
    async def test_editarea_set_readonly_on(
        self, db_session: Session, admin_sender_key: str, sample_areas: list[Area]
    ):
        """Test setting area to readonly."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(
            "/editarea tech readonly on", admin_sender_key
        )

        assert response is not None
        assert "sola lettura" in response.lower()

        area = db_session.query(Area).filter_by(name="tech").first()
        assert area.is_readonly is True

    @pytest.mark.asyncio
    async def test_editarea_set_readonly_off(
        self, db_session: Session, admin_sender_key: str, sample_areas: list[Area]
    ):
        """Test setting area to writable."""
        # First set to readonly
        area = db_session.query(Area).filter_by(name="tech").first()
        area.is_readonly = True
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(
            "/editarea tech readonly off", admin_sender_key
        )

        assert response is not None
        assert "scrittura abilitata" in response.lower()

        db_session.refresh(area)
        assert area.is_readonly is False

    @pytest.mark.asyncio
    async def test_editarea_set_public_off(
        self, db_session: Session, admin_sender_key: str, sample_areas: list[Area]
    ):
        """Test hiding an area."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(
            "/editarea tech public off", admin_sender_key
        )

        assert response is not None
        assert "nascosta" in response.lower()

        area = db_session.query(Area).filter_by(name="tech").first()
        assert area.is_public is False

    @pytest.mark.asyncio
    async def test_editarea_set_public_on(
        self, db_session: Session, admin_sender_key: str, sample_areas: list[Area]
    ):
        """Test making area public."""
        # First hide it
        area = db_session.query(Area).filter_by(name="tech").first()
        area.is_public = False
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(
            "/editarea tech public on", admin_sender_key
        )

        assert response is not None
        assert "pubblica" in response.lower()

        db_session.refresh(area)
        assert area.is_public is True

    @pytest.mark.asyncio
    async def test_editarea_area_not_found(
        self, db_session: Session, admin_sender_key: str
    ):
        """Test editing non-existent area."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(
            "/editarea nonexistent desc Test", admin_sender_key
        )

        assert response is not None
        assert "non trovata" in response.lower()

    @pytest.mark.asyncio
    async def test_editarea_unknown_property(
        self, db_session: Session, admin_sender_key: str, sample_areas: list[Area]
    ):
        """Test editing with unknown property."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(
            "/editarea tech unknown value", admin_sender_key
        )

        assert response is not None
        assert "sconosciuta" in response.lower()

    @pytest.mark.asyncio
    async def test_editarea_desc_no_value(
        self, db_session: Session, admin_sender_key: str, sample_areas: list[Area]
    ):
        """Test changing description without value."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(
            "/editarea tech desc", admin_sender_key
        )

        assert response is not None
        assert "specifica" in response.lower()

    @pytest.mark.asyncio
    async def test_editarea_readonly_invalid_value(
        self, db_session: Session, admin_sender_key: str, sample_areas: list[Area]
    ):
        """Test readonly with invalid value."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(
            "/editarea tech readonly maybe", admin_sender_key
        )

        assert response is not None
        assert "on/off" in response.lower()


class TestListAreasAdminCommand:
    """Tests for /listareas command."""

    @pytest.mark.asyncio
    async def test_listareas_non_admin_denied(
        self, db_session: Session, test_sender_key: str
    ):
        """Test non-admin cannot use /listareas."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/listareas", test_sender_key)

        assert response is not None
        assert "permesso negato" in response.lower()

    @pytest.mark.asyncio
    async def test_listareas_shows_areas(
        self, db_session: Session, admin_sender_key: str, sample_areas: list[Area]
    ):
        """Test listareas shows all areas."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/listareas", admin_sender_key)

        assert response is not None
        assert "aree" in response.lower()
        assert "generale" in response.lower()
        assert "tech" in response.lower()

    @pytest.mark.asyncio
    async def test_listareas_shows_flags(
        self, db_session: Session, admin_sender_key: str, sample_areas: list[Area]
    ):
        """Test listareas shows readonly and hidden flags."""
        # Set one area to readonly
        area = db_session.query(Area).filter_by(name="tech").first()
        area.is_readonly = True
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/listareas", admin_sender_key)

        assert response is not None
        assert "ro" in response.lower()

    @pytest.mark.asyncio
    async def test_listareas_shows_hidden_areas(
        self, db_session: Session, admin_sender_key: str
    ):
        """Test listareas shows hidden areas."""
        # Create hidden area
        hidden = Area(name="hidden", is_public=False)
        db_session.add(hidden)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/listareas", admin_sender_key)

        assert response is not None
        assert "hidden" in response.lower()

    @pytest.mark.asyncio
    async def test_listareas_shows_message_count(
        self, db_session: Session, admin_sender_key: str, sample_areas: list[Area]
    ):
        """Test listareas shows message count."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/listareas", admin_sender_key)

        assert response is not None
        assert "msg" in response.lower()

    @pytest.mark.asyncio
    async def test_listareas_shows_total(
        self, db_session: Session, admin_sender_key: str, sample_areas: list[Area]
    ):
        """Test listareas shows total count."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/listareas", admin_sender_key)

        assert response is not None
        assert "totale" in response.lower()


class TestAreaWorkflow:
    """Tests for complete area management workflows."""

    @pytest.mark.asyncio
    async def test_create_modify_delete_workflow(
        self, db_session: Session, admin_sender_key: str
    ):
        """Test complete area lifecycle."""
        dispatcher = CommandDispatcher(session=db_session)

        # Create area
        response = await dispatcher.dispatch(
            "/newarea workflow Test workflow area", admin_sender_key
        )
        assert "creata" in response.lower()

        # Modify description
        response = await dispatcher.dispatch(
            "/editarea workflow desc Updated description", admin_sender_key
        )
        assert "aggiornata" in response.lower()

        # Set readonly
        response = await dispatcher.dispatch(
            "/editarea workflow readonly on", admin_sender_key
        )
        assert "sola lettura" in response.lower()

        # Verify with listareas
        response = await dispatcher.dispatch("/listareas", admin_sender_key)
        assert "workflow" in response.lower()
        assert "ro" in response.lower()

        # Delete
        response = await dispatcher.dispatch("/delarea workflow", admin_sender_key)
        assert "eliminata" in response.lower()

        # Verify deleted
        area = db_session.query(Area).filter_by(name="workflow").first()
        assert area is None
