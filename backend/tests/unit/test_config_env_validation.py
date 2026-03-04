import pytest

from app.core.config import Settings


def test_dev_allows_memory_broker_with_eager_true():
    cfg = Settings(
        APP_ENV="dev",
        CELERY_BROKER_URL="memory://",
        CELERY_TASK_ALWAYS_EAGER=True,
    )
    assert cfg.APP_ENV == "dev"


def test_dev_rejects_memory_broker_when_eager_false():
    with pytest.raises(ValueError):
        Settings(
            APP_ENV="dev",
            CELERY_BROKER_URL="memory://",
            CELERY_TASK_ALWAYS_EAGER=False,
        )


def test_staging_rejects_memory_broker():
    with pytest.raises(ValueError):
        Settings(
            APP_ENV="staging",
            CELERY_BROKER_URL="memory://",
            CELERY_TASK_ALWAYS_EAGER=False,
        )


def test_prod_rejects_eager_true():
    with pytest.raises(ValueError):
        Settings(
            APP_ENV="prod",
            CELERY_BROKER_URL="redis://127.0.0.1:6379/0",
            CELERY_TASK_ALWAYS_EAGER=True,
        )
