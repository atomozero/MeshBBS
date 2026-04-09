"""
Tests for promote/demote/staff commands.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import pytest
from sqlalchemy.orm import Session

from bbs.commands.dispatcher import CommandDispatcher
from bbs.models.user import User


class TestPromoteCommand:
    """Tests for /promote command."""

    @pytest.mark.asyncio
    async def test_promote_no_args(self, db_session: Session, admin_sender_key: str):
        """Test /promote without arguments shows usage."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!promote", admin_sender_key)

        assert response is not None
        assert "uso" in response.lower()

    @pytest.mark.asyncio
    async def test_promote_non_admin_denied(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str
    ):
        """Test non-admin cannot use /promote."""
        target = User(public_key=test_sender_key_2, nickname="Target")
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!promote Target", test_sender_key)

        assert response is not None
        assert "permesso negato" in response.lower()

    @pytest.mark.asyncio
    async def test_promote_user_not_found(
        self, db_session: Session, admin_sender_key: str
    ):
        """Test /promote with non-existent user."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!promote NonExistent", admin_sender_key)

        assert response is not None
        assert "non trovato" in response.lower()

    @pytest.mark.asyncio
    async def test_promote_to_moderator(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test promoting user to moderator."""
        target = User(public_key=test_sender_key_2, nickname="NewMod")
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!promote NewMod", admin_sender_key)

        assert response is not None
        assert "moderatore" in response.lower()

        db_session.refresh(target)
        assert target.is_moderator is True
        assert target.is_admin is False

    @pytest.mark.asyncio
    async def test_promote_to_admin(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test promoting user to admin."""
        target = User(public_key=test_sender_key_2, nickname="NewAdmin")
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!promote NewAdmin admin", admin_sender_key)

        assert response is not None
        assert "admin" in response.lower()

        db_session.refresh(target)
        assert target.is_admin is True
        assert target.is_moderator is True  # Admins are also mods

    @pytest.mark.asyncio
    async def test_promote_cannot_promote_self(
        self, db_session: Session, admin_sender_key: str
    ):
        """Test admin cannot promote themselves."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(f"!promote {admin_sender_key[:8]}", admin_sender_key)

        assert response is not None
        assert "te stesso" in response.lower()

    @pytest.mark.asyncio
    async def test_promote_already_moderator(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test promoting already moderator to moderator."""
        target = User(public_key=test_sender_key_2, nickname="ExistingMod", is_moderator=True)
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!promote ExistingMod", admin_sender_key)

        assert response is not None
        assert "già moderatore" in response.lower()

    @pytest.mark.asyncio
    async def test_promote_already_admin(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test promoting already admin."""
        target = User(public_key=test_sender_key_2, nickname="ExistingAdmin", is_admin=True)
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!promote ExistingAdmin admin", admin_sender_key)

        assert response is not None
        assert "già admin" in response.lower()

    @pytest.mark.asyncio
    async def test_promote_admin_cannot_be_promoted_to_mod(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test admin cannot be 'promoted' to moderator."""
        target = User(public_key=test_sender_key_2, nickname="Admin2", is_admin=True)
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!promote Admin2", admin_sender_key)

        assert response is not None
        assert "già admin" in response.lower()

    @pytest.mark.asyncio
    async def test_promote_banned_user(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test cannot promote banned user."""
        target = User(public_key=test_sender_key_2, nickname="Banned", is_banned=True)
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!promote Banned", admin_sender_key)

        assert response is not None
        assert "bannato" in response.lower()

    @pytest.mark.asyncio
    async def test_promote_moderator_to_admin(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test promoting moderator to admin."""
        target = User(public_key=test_sender_key_2, nickname="ModToAdmin", is_moderator=True)
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!promote ModToAdmin admin", admin_sender_key)

        assert response is not None
        assert "admin" in response.lower()

        db_session.refresh(target)
        assert target.is_admin is True


class TestDemoteCommand:
    """Tests for /demote command."""

    @pytest.mark.asyncio
    async def test_demote_no_args(self, db_session: Session, admin_sender_key: str):
        """Test /demote without arguments shows usage."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!demote", admin_sender_key)

        assert response is not None
        assert "uso" in response.lower()

    @pytest.mark.asyncio
    async def test_demote_non_admin_denied(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str
    ):
        """Test non-admin cannot use /demote."""
        target = User(public_key=test_sender_key_2, nickname="Mod", is_moderator=True)
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!demote Mod", test_sender_key)

        assert response is not None
        assert "permesso negato" in response.lower()

    @pytest.mark.asyncio
    async def test_demote_moderator_to_user(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test demoting moderator to regular user."""
        target = User(public_key=test_sender_key_2, nickname="ExMod", is_moderator=True)
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!demote ExMod", admin_sender_key)

        assert response is not None
        assert "utente" in response.lower()

        db_session.refresh(target)
        assert target.is_moderator is False
        assert target.is_admin is False

    @pytest.mark.asyncio
    async def test_demote_admin_to_moderator(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test demoting admin to moderator."""
        target = User(public_key=test_sender_key_2, nickname="ExAdmin", is_admin=True, is_moderator=True)
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!demote ExAdmin", admin_sender_key)

        assert response is not None
        assert "moderatore" in response.lower()

        db_session.refresh(target)
        assert target.is_admin is False
        assert target.is_moderator is True  # Still moderator

    @pytest.mark.asyncio
    async def test_demote_cannot_demote_self(
        self, db_session: Session, admin_sender_key: str
    ):
        """Test admin cannot demote themselves."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(f"!demote {admin_sender_key[:8]}", admin_sender_key)

        assert response is not None
        assert "te stesso" in response.lower()

    @pytest.mark.asyncio
    async def test_demote_regular_user(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test demoting regular user (already normal)."""
        target = User(public_key=test_sender_key_2, nickname="Regular")
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!demote Regular", admin_sender_key)

        assert response is not None
        assert "già un utente normale" in response.lower()

    @pytest.mark.asyncio
    async def test_demote_user_not_found(
        self, db_session: Session, admin_sender_key: str
    ):
        """Test /demote with non-existent user."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!demote NonExistent", admin_sender_key)

        assert response is not None
        assert "non trovato" in response.lower()


class TestStaffCommand:
    """Tests for /staff command."""

    @pytest.mark.asyncio
    async def test_staff_no_staff(self, db_session: Session, test_sender_key: str):
        """Test /staff with no staff configured."""
        # Clear admin from fixture by creating a fresh user
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!staff", test_sender_key)

        assert response is not None
        # Either shows no staff or shows the admin from fixture
        assert "staff" in response.lower()

    @pytest.mark.asyncio
    async def test_staff_shows_admins(
        self, db_session: Session, test_sender_key: str, admin_sender_key: str
    ):
        """Test /staff shows admin users."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!staff", test_sender_key)

        assert response is not None
        assert "[a]" in response.lower()
        assert "admin" in response.lower()

    @pytest.mark.asyncio
    async def test_staff_shows_moderators(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str
    ):
        """Test /staff shows moderators."""
        mod = User(public_key=test_sender_key_2, nickname="ModUser", is_moderator=True)
        db_session.add(mod)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!staff", test_sender_key)

        assert response is not None
        assert "[m]" in response.lower()
        assert "moduser" in response.lower()

    @pytest.mark.asyncio
    async def test_staff_shows_both(
        self, db_session: Session, test_sender_key: str, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test /staff shows both admins and moderators."""
        mod = User(public_key=test_sender_key_2, nickname="ModUser", is_moderator=True)
        db_session.add(mod)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!staff", test_sender_key)

        assert response is not None
        assert "[a]" in response.lower()
        assert "[m]" in response.lower()
        assert "1 admin" in response.lower()
        assert "1 mod" in response.lower()

    @pytest.mark.asyncio
    async def test_staff_alias_mods(
        self, db_session: Session, test_sender_key: str, admin_sender_key: str
    ):
        """Test /mods alias works."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/mods", test_sender_key)

        assert response is not None
        assert "staff" in response.lower()

    @pytest.mark.asyncio
    async def test_staff_alias_admins(
        self, db_session: Session, test_sender_key: str, admin_sender_key: str
    ):
        """Test /admins alias works."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/admins", test_sender_key)

        assert response is not None
        assert "staff" in response.lower()

    @pytest.mark.asyncio
    async def test_staff_available_to_all(
        self, db_session: Session, test_sender_key: str, admin_sender_key: str
    ):
        """Test /staff is available to non-admin users."""
        # Regular user should be able to use /staff
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!staff", test_sender_key)

        assert response is not None
        # Should not be "permesso negato"
        assert "permesso negato" not in response.lower()


class TestRoleDisplay:
    """Tests for role display property."""

    def test_role_display_admin(self, db_session: Session):
        """Test role display for admin."""
        user = User(public_key="X" * 64, is_admin=True)
        assert user.role_display == "Admin"

    def test_role_display_moderator(self, db_session: Session):
        """Test role display for moderator."""
        user = User(public_key="X" * 64, is_moderator=True)
        assert user.role_display == "Moderatore"

    def test_role_display_user(self, db_session: Session):
        """Test role display for regular user."""
        user = User(public_key="X" * 64)
        assert user.role_display == "Utente"

    def test_role_display_admin_priority(self, db_session: Session):
        """Test admin role takes priority over moderator."""
        user = User(public_key="X" * 64, is_admin=True, is_moderator=True)
        assert user.role_display == "Admin"


class TestPromoteDemoteWorkflow:
    """Tests for complete promote/demote workflows."""

    @pytest.mark.asyncio
    async def test_full_promotion_workflow(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test user -> moderator -> admin workflow."""
        target = User(public_key=test_sender_key_2, nickname="Rising")
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)

        # Promote to moderator
        response = await dispatcher.dispatch("!promote Rising", admin_sender_key)
        assert "moderatore" in response.lower()

        db_session.refresh(target)
        assert target.is_moderator is True
        assert target.is_admin is False

        # Promote to admin
        response = await dispatcher.dispatch("!promote Rising admin", admin_sender_key)
        assert "admin" in response.lower()

        db_session.refresh(target)
        assert target.is_admin is True

    @pytest.mark.asyncio
    async def test_full_demotion_workflow(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test admin -> moderator -> user workflow."""
        target = User(public_key=test_sender_key_2, nickname="Falling", is_admin=True, is_moderator=True)
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)

        # Demote from admin to moderator
        response = await dispatcher.dispatch("!demote Falling", admin_sender_key)
        assert "moderatore" in response.lower()

        db_session.refresh(target)
        assert target.is_admin is False
        assert target.is_moderator is True

        # Demote from moderator to user
        response = await dispatcher.dispatch("!demote Falling", admin_sender_key)
        assert "utente" in response.lower()

        db_session.refresh(target)
        assert target.is_moderator is False
