import os


def database_url() -> str:
    """URL de conexión. En Docker Compose se construye a partir de las variables POSTGRES_*."""
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    user = os.environ.get("POSTGRES_USER", "arqueo")
    password = os.environ.get("POSTGRES_PASSWORD", "")  # sin valor por defecto: se define en .env
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    name = os.environ.get("POSTGRES_DB", "arqueo")
    credentials = f"{user}:{password}" if password else user
    return f"postgresql+psycopg://{credentials}@{host}:{port}/{name}"


DATA_LICENSE = os.environ.get("DATA_LICENSE", "CC-BY-4.0")