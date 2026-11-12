"""Safe pre-release configuration diagnostics, never environment/secret values."""

from pydantic import ValidationError

from app.core.config import Settings


def main():
    try:
        settings = Settings()
        if settings.app_env != "production" or not settings.serve_frontend:
            raise ValueError()
    except ValidationError as error:
        fields = {
            str(item["loc"][0]) if item["loc"] else "security policy"
            for item in error.errors(include_input=False, include_context=False)
        }
        print("Deployment configuration invalid: " + ", ".join(sorted(fields)))
        raise SystemExit(1) from None
    except Exception:
        print("Deployment requires production mode and SERVE_FRONTEND=true.")
        raise SystemExit(1) from None
    print("Deployment configuration valid; provider probes are separate.")


if __name__ == "__main__":
    main()
