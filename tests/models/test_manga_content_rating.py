import unittest
from app.models.manga import Manga


class MangaModelContentRatingTests(unittest.TestCase):
    def test_manga_has_content_rating_field(self):
        manga = Manga(id="1", title="Test", contentRating="suggestive")
        self.assertEqual(manga.contentRating, "suggestive")

    def test_manga_content_rating_defaults_to_none(self):
        manga = Manga(id="1", title="Test")
        self.assertIsNone(manga.contentRating)

    def test_manga_content_rating_accepts_all_values(self):
        for rating in ["safe", "suggestive", "erotica", "pornographic"]:
            manga = Manga(id="1", title="Test", contentRating=rating)
            self.assertEqual(manga.contentRating, rating)

    def test_manga_content_rating_none_explicit(self):
        manga = Manga(id="1", title="Test", contentRating=None)
        self.assertIsNone(manga.contentRating)


if __name__ == "__main__":
    unittest.main()
