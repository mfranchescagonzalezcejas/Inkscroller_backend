"""Tests for FastAPI dependency-injection helpers."""

import unittest
from unittest.mock import AsyncMock

from app.core.dependencies import get_user_language
from app.core.firebase_auth import FirebaseTokenPayload
from app.models.user import ReadingPreferences


class TestGetUserLanguage(unittest.IsolatedAsyncioTestCase):
    async def test_get_user_language_returns_query_param(self):
        user_service = AsyncMock()

        result = await get_user_language(
            lang="es", user=None, user_service=user_service
        )

        self.assertEqual(result, "es")
        user_service.get_preferences.assert_not_awaited()

    async def test_get_user_language_returns_preference_for_auth_user(self):
        user_service = AsyncMock()
        user_service.get_preferences.return_value = ReadingPreferences(
            firebase_uid="uid-1",
            default_language="pt-br",
            updated_at="2024-01-01T00:00:00Z",
        )
        user = FirebaseTokenPayload(uid="uid-1", email="a@b.com")

        result = await get_user_language(
            lang=None, user=user, user_service=user_service
        )

        self.assertEqual(result, "pt-br")
        user_service.get_preferences.assert_awaited_once_with("uid-1")

    async def test_get_user_language_returns_en_for_guest(self):
        user_service = AsyncMock()

        result = await get_user_language(
            lang=None, user=None, user_service=user_service
        )

        self.assertEqual(result, "en")
        user_service.get_preferences.assert_not_awaited()

    async def test_get_user_language_strips_whitespace(self):
        user_service = AsyncMock()

        result = await get_user_language(
            lang="  es  ", user=None, user_service=user_service
        )

        self.assertEqual(result, "es")

    async def test_get_user_language_ignores_empty_query_param(self):
        user_service = AsyncMock()
        user_service.get_preferences.return_value = ReadingPreferences(
            firebase_uid="uid-1",
            default_language="fr",
            updated_at="2024-01-01T00:00:00Z",
        )
        user = FirebaseTokenPayload(uid="uid-1", email="a@b.com")

        result = await get_user_language(
            lang="   ", user=user, user_service=user_service
        )

        self.assertEqual(result, "fr")


if __name__ == "__main__":
    unittest.main()
