from gqmrmed.config import get_settings


if __name__ == "__main__":
    settings = get_settings()
    print(f"{settings.app_name} {settings.app_version}")
