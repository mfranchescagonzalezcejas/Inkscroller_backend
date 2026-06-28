import os
import unittest
from unittest.mock import patch

from app.core.config import Settings


def create_app_with_settings(settings: Settings):
    with patch.dict(
        os.environ,
        {"ENVIRONMENT": "development", "CORS_ORIGINS": "http://localhost:5173"},
        clear=True,
    ):
        with patch("app.core.config.settings", Settings()):
            main_module = __import__("main")

    with patch.object(main_module, "settings", settings):
        return main_module.create_app()


class CorsConfigurationTests(unittest.TestCase):
    def test_production_wildcard_cors_with_credentials_is_rejected(self):
        with patch.dict(
            os.environ,
            {"ENVIRONMENT": "production", "CORS_ORIGINS": "*"},
            clear=True,
        ):
            production_settings = Settings()

        with self.assertRaisesRegex(RuntimeError, "Unsafe CORS configuration"):
            create_app_with_settings(production_settings)

    def test_railway_production_overrides_stale_development_environment(self):
        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "development",
                "RAILWAY_ENVIRONMENT_NAME": "production",
                "CORS_ORIGINS": "*",
            },
            clear=True,
        ):
            production_settings = Settings()

        self.assertEqual(production_settings.environment, "production")

        with self.assertRaisesRegex(RuntimeError, "Unsafe CORS configuration"):
            create_app_with_settings(production_settings)

    def test_blank_production_cors_origins_are_rejected(self):
        with patch.dict(
            os.environ,
            {"ENVIRONMENT": "production", "CORS_ORIGINS": "   "},
            clear=True,
        ):
            production_settings = Settings()

        self.assertEqual(production_settings.cors_origins, [])

        with self.assertRaisesRegex(RuntimeError, "CORS_ORIGINS must include"):
            create_app_with_settings(production_settings)

    def test_production_mixed_wildcard_cors_origins_are_rejected(self):
        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "production",
                "CORS_ORIGINS": "https://inkscroller-app.web.app,*",
            },
            clear=True,
        ):
            production_settings = Settings()

        with self.assertRaisesRegex(RuntimeError, "Unsafe CORS configuration"):
            create_app_with_settings(production_settings)

    def test_production_explicit_cors_origins_are_accepted(self):
        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "production",
                "CORS_ORIGINS": "https://inkscroller-app.web.app,https://devdigi.dev",
            },
            clear=True,
        ):
            production_settings = Settings()

        app = create_app_with_settings(production_settings)

        self.assertEqual(
            production_settings.cors_origins,
            ["https://inkscroller-app.web.app", "https://devdigi.dev"],
        )
        self.assertEqual(app.title, "Inkscroller API")

    def test_development_wildcard_cors_is_allowed_when_explicit(self):
        with patch.dict(
            os.environ,
            {"ENVIRONMENT": "development", "CORS_ORIGINS": "*"},
            clear=True,
        ):
            development_settings = Settings()

        app = create_app_with_settings(development_settings)

        self.assertEqual(development_settings.cors_origins, ["*"])
        self.assertEqual(app.title, "Inkscroller API")


if __name__ == "__main__":
    unittest.main()
