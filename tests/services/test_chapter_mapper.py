import unittest

from app.services.chapter_mapper import map_mangadex_chapter


class ChapterMapperTests(unittest.TestCase):
    def test_map_chapter_extracts_scanlation_group_name(self):
        payload = {
            "id": "chapter-1",
            "attributes": {
                "chapter": "12",
                "title": "The Return",
                "pages": 22,
                "externalUrl": None,
            },
            "relationships": [
                {
                    "id": "group-1",
                    "type": "scanlation_group",
                    "attributes": {"name": "Luna Scans"},
                }
            ],
        }

        chapter = map_mangadex_chapter(payload)

        self.assertEqual(chapter["scanlation_group"], "Luna Scans")

    def test_map_chapter_uses_scanlation_group_id_as_fallback(self):
        payload = {
            "id": "chapter-1",
            "attributes": {
                "chapter": "12",
                "title": "The Return",
                "pages": 22,
                "externalUrl": None,
            },
            "relationships": [
                {
                    "id": "group-raw-id",
                    "type": "scanlation_group",
                }
            ],
        }

        chapter = map_mangadex_chapter(payload)

        self.assertEqual(chapter["scanlation_group"], "group-raw-id")


if __name__ == "__main__":
    unittest.main()
