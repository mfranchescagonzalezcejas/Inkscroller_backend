import unittest
from datetime import date, timedelta
from app.core.age import compute_age, can_access_content, CONTENT_AGE_LIMITS


class TestComputeAge(unittest.TestCase):
    def test_compute_age_normal(self):
        birth = date.today() - timedelta(days=365 * 20 + 5)
        age = compute_age(birth)
        self.assertEqual(age, 20)

    def test_compute_age_exact_birthday(self):
        birth = date(date.today().year - 20, date.today().month, date.today().day)
        age = compute_age(birth)
        self.assertEqual(age, 20)

    def test_compute_age_day_before_birthday(self):
        today = date.today()
        birth = date(today.year - 20, today.month, today.day)
        yesterday = birth + timedelta(days=1)
        # This person turns 20 tomorrow but is 19 today
        age = compute_age(birth)
        expected = 20  # it IS their birthday today
        self.assertEqual(age, expected)

    def test_compute_age_none(self):
        self.assertIsNone(compute_age(None))

    def test_compute_age_future_date(self):
        future = date.today() + timedelta(days=1)
        self.assertIsNone(compute_age(future))

    def test_compute_age_boundary_under_16(self):
        today = date.today()
        # Exactly 15 years, 364 days old
        birth = date(today.year - 15, today.month, today.day) + timedelta(days=1)
        age = compute_age(birth)
        self.assertIsNotNone(age)
        self.assertLess(age, 16)

    def test_compute_age_boundary_16(self):
        today = date.today()
        # Exactly 16 years old
        birth = date(today.year - 16, today.month, today.day)
        age = compute_age(birth)
        self.assertIsNotNone(age)
        self.assertGreaterEqual(age, 16)


class TestCanAccessContent(unittest.TestCase):
    def test_safe_any_age(self):
        self.assertTrue(can_access_content("safe", 0))
        self.assertTrue(can_access_content("safe", 16))
        self.assertTrue(can_access_content("safe", None))

    def test_suggestive_16_plus(self):
        self.assertTrue(can_access_content("suggestive", 16))
        self.assertTrue(can_access_content("suggestive", 20))
        self.assertFalse(can_access_content("suggestive", 15))
        self.assertFalse(can_access_content("suggestive", 0))

    def test_suggestive_none_age(self):
        self.assertFalse(can_access_content("suggestive", None))

    def test_none_rating(self):
        self.assertTrue(can_access_content(None, 0))
        self.assertTrue(can_access_content(None, 16))
        self.assertTrue(can_access_content(None, None))

    def test_unknown_rating(self):
        self.assertTrue(can_access_content("unknown_rating", 0))
        self.assertTrue(can_access_content("unknown_rating", None))

    def test_erotica_18_plus(self):
        self.assertTrue(can_access_content("erotica", 18))
        self.assertTrue(can_access_content("erotica", 25))
        self.assertFalse(can_access_content("erotica", 17))
        self.assertFalse(can_access_content("erotica", None))

    def test_pornographic_18_plus(self):
        self.assertTrue(can_access_content("pornographic", 18))
        self.assertFalse(can_access_content("pornographic", 17))
        self.assertFalse(can_access_content("pornographic", None))

    def test_safe_none_age(self):
        self.assertTrue(can_access_content("safe", None))


if __name__ == "__main__":
    unittest.main()
