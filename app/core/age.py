"""Age computation and content restriction rules.

Maps MangaDex content ratings to minimum age thresholds
and provides helpers to evaluate access.
"""

from datetime import date

CONTENT_AGE_LIMITS: dict[str, int] = {
    "safe": 0,
    "suggestive": 16,
    "erotica": 18,
    "pornographic": 18,
}


def compute_age(birth_date: date | None) -> int | None:
    """Compute age from birth_date. Returns None if invalid."""
    if birth_date is None:
        return None
    today = date.today()
    if birth_date > today:
        return None
    return (
        today.year
        - birth_date.year
        - ((today.month, today.day) < (birth_date.month, birth_date.day))
    )


def can_access_content(
    content_rating: str | None,
    user_age: int | None,
) -> bool:
    """Determine if a user can access content with the given rating.

    Fail-closed for unrecognised rating strings: if MangaDex sends a rating
    this code does not know about, the content is blocked.  ``None`` (missing
    attribute) is allowed through — it is a data gap rather than a content
    decision; callers that want a stricter policy for unrated content (e.g.
    guest users) implement it in their own filter logic.
    """
    if content_rating is None:
        return True  # missing attribute → allow (data gap, not a rating)
    min_age = CONTENT_AGE_LIMITS.get(content_rating)
    if min_age is None:
        return False  # unknown rating string → fail-closed
    if user_age is None:
        return min_age == 0  # only safe (age 0) for guests/unknown
    return user_age >= min_age
