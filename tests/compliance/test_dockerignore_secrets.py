"""Docker build context safety checks."""

from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_DOCKERIGNORE_PATTERNS = (
    ".env",
    ".env.*",
    "!.env.example",
    ".env.local",
    ".env.*.local",
    "serviceAccountKey.json",
    "*serviceAccount*.json",
    "firebase-adminsdk-*.json",
    "*-firebase-adminsdk-*.json",
    "*credentials*.json",
    "gcloud-*.json",
    "docker-compose.override.yml",
    "*.db",
    "*.db-shm",
    "*.db-wal",
)

REQUIRED_ENV_PATTERN_SEQUENCE = (
    ".env",
    ".env.*",
    "!.env.example",
    ".env.local",
    ".env.*.local",
)


def _load_dockerignore_patterns() -> list[str]:
    dockerignore = REPO_ROOT / ".dockerignore"
    return [
        line.strip()
        for line in dockerignore.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _pattern_positions(
    patterns: list[str], required_patterns: tuple[str, ...]
) -> dict[str, list[int]]:
    return {
        required_pattern: [
            index for index, pattern in enumerate(patterns) if pattern == required_pattern
        ]
        for required_pattern in required_patterns
    }


class TestDockerignoreSecrets(unittest.TestCase):
    def test_dockerignore_excludes_local_secrets_from_build_context(self):
        patterns = _load_dockerignore_patterns()
        pattern_set = set(patterns)

        missing_patterns = set(REQUIRED_DOCKERIGNORE_PATTERNS) - pattern_set

        self.assertEqual(
            missing_patterns,
            set(),
            msg=(
                ".dockerignore is missing sensitive build-context exclusions: "
                f"{sorted(missing_patterns)}"
            ),
        )

        env_pattern_positions = _pattern_positions(
            patterns, REQUIRED_ENV_PATTERN_SEQUENCE
        )

        for left_pattern, right_pattern in zip(
            REQUIRED_ENV_PATTERN_SEQUENCE,
            REQUIRED_ENV_PATTERN_SEQUENCE[1:],
        ):
            self.assertLess(
                max(env_pattern_positions[left_pattern]),
                min(env_pattern_positions[right_pattern]),
                msg=(
                    ".dockerignore environment rules must keep this relative order: "
                    f"{list(REQUIRED_ENV_PATTERN_SEQUENCE)}"
                ),
            )


if __name__ == "__main__":
    unittest.main()
