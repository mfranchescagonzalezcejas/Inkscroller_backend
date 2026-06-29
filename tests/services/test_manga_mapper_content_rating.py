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


if __name__ == "__main__":
    unittest.main()
