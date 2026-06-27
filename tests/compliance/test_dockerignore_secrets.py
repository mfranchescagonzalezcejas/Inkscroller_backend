"""Docker build context safety checks."""

from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_DOCKERIGNORE_PATTERNS = {
    ".env",
    ".env.*",
    "!.env.example",
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
}


def _load_dockerignore_patterns() -> set[str]:
    dockerignore = REPO_ROOT / ".dockerignore"
    return {
        line.strip()
        for line in dockerignore.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


class TestDockerignoreSecrets(unittest.TestCase):
    def test_dockerignore_excludes_local_secrets_from_build_context(self):
        patterns = _load_dockerignore_patterns()

        missing_patterns = REQUIRED_DOCKERIGNORE_PATTERNS - patterns

        self.assertEqual(
            missing_patterns,
            set(),
            msg=(
                ".dockerignore is missing sensitive build-context exclusions: "
                f"{sorted(missing_patterns)}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
