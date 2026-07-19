import unittest

from app.services.manga_mapper import map_mangadex_manga


class MangaMapperContentRatingTests(unittest.TestCase):
    def test_map_mangadex_extracts_content_rating(self):
        item = {
            "id": "manga-001",
            "attributes": {
                "title": {"en": "Test Manga"},
                "contentRating": "suggestive",
                "status": "ongoing",
                "publicationDemographic": "shounen",
                "tags": [],
            },
            "relationships": [],
        }
        result = map_mangadex_manga(item)
        self.assertEqual(result["contentRating"], "suggestive")

    def test_map_mangadex_content_rating_none_when_missing(self):
        item = {
            "id": "manga-002",
            "attributes": {
                "title": {"en": "No Rating Manga"},
                "status": "completed",
            },
            "relationships": [],
        }
        result = map_mangadex_manga(item)
        self.assertIsNone(result["contentRating"])

    def test_map_mangadex_content_rating_safe(self):
        item = {
            "id": "manga-003",
            "attributes": {
                "title": {"en": "Safe Manga"},
                "contentRating": "safe",
                "tags": [],
            },
            "relationships": [],
        }
        result = map_mangadex_manga(item)
        self.assertEqual(result["contentRating"], "safe")

    def test_map_mangadex_content_rating_erotica(self):
        item = {
            "id": "manga-004",
            "attributes": {
                "title": {"en": "Erotica Manga"},
                "contentRating": "erotica",
                "tags": [],
            },
            "relationships": [],
        }
        result = map_mangadex_manga(item)
        self.assertEqual(result["contentRating"], "erotica")

    def test_normalize_none_demographic(self):
        """'none' string is normalized to Python None."""
        item = {
            "id": "manga-010",
            "attributes": {
                "title": {"en": "No Demo"},
                "publicationDemographic": "none",
                "contentRating": "safe",
                "tags": [],
            },
            "relationships": [],
        }
        result = map_mangadex_manga(item)
        self.assertIsNone(result["demographic"])

    def test_keeps_valid_demographic(self):
        """Valid demographic values are passed through unchanged."""
        item = {
            "id": "manga-011",
            "attributes": {
                "title": {"en": "Shounen"},
                "publicationDemographic": "shounen",
                "contentRating": "safe",
                "tags": [],
            },
            "relationships": [],
        }
        result = map_mangadex_manga(item)
        self.assertEqual(result["demographic"], "shounen")

    def test_keeps_none_demographic(self):
        """JSON null stays Python None."""
        item = {
            "id": "manga-012",
            "attributes": {
                "title": {"en": "Null Demo"},
                "publicationDemographic": None,
                "contentRating": "safe",
                "tags": [],
            },
            "relationships": [],
        }
        result = map_mangadex_manga(item)
        self.assertIsNone(result["demographic"])

    def test_map_mangadex_content_rating_pornographic(self):
        item = {
            "id": "manga-005",
            "attributes": {
                "title": {"en": "Pornographic Manga"},
                "contentRating": "pornographic",
                "tags": [],
            },
            "relationships": [],
        }
        result = map_mangadex_manga(item)
        self.assertEqual(result["contentRating"], "pornographic")


class MangaTypeMappingTests(unittest.TestCase):
    """Map originalLanguage from MangaDex to type field."""

    def _make_item(self, original_language: str | None = None) -> dict:
        attrs: dict = {
            "title": {"en": "Test Manga"},
            "contentRating": "safe",
            "tags": [],
        }
        if original_language is not None:
            attrs["originalLanguage"] = original_language
        return {
            "id": "manga-type-001",
            "attributes": attrs,
            "relationships": [],
        }

    def test_japanese_is_manga(self) -> None:
        """ja → type=manga."""
        result = map_mangadex_manga(self._make_item("ja"))
        self.assertEqual(result["type"], "manga")

    def test_korean_is_manhwa(self) -> None:
        """ko → type=manhwa."""
        result = map_mangadex_manga(self._make_item("ko"))
        self.assertEqual(result["type"], "manhwa")

    def test_chinese_is_manhua(self) -> None:
        """zh → type=manhua."""
        result = map_mangadex_manga(self._make_item("zh"))
        self.assertEqual(result["type"], "manhua")

    def test_english_is_null(self) -> None:
        """en → type=None."""
        result = map_mangadex_manga(self._make_item("en"))
        self.assertIsNone(result["type"])

    def test_french_is_null(self) -> None:
        """fr → type=None."""
        result = map_mangadex_manga(self._make_item("fr"))
        self.assertIsNone(result["type"])

    def test_missing_original_language_is_null(self) -> None:
        """No originalLanguage attribute → type=None."""
        result = map_mangadex_manga(self._make_item(None))
        self.assertIsNone(result["type"])

    def test_original_language_absent_from_attributes(self) -> None:
        """Attributes dict without originalLanguage → type=None."""
        item = {
            "id": "manga-type-002",
            "attributes": {
                "title": {"en": "No Lang Manga"},
                "contentRating": "safe",
                "tags": [],
            },
            "relationships": [],
        }
        result = map_mangadex_manga(item)
        self.assertIsNone(result["type"])


if __name__ == "__main__":
    unittest.main()
