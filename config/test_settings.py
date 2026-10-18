import base64

from .settings import *


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

BACKUP_DATA_ENCRYPTION_ACTIVE_VERSION = "v1"
BACKUP_DATA_ENCRYPTION_KEYS = {
    "v1": base64.urlsafe_b64encode(b"test-backup-key-32-bytes-long!!!!"[:32]).decode("ascii")
}
PLATFORM_TOKEN_ENCRYPTION_ACTIVE_VERSION = "v1"
PLATFORM_TOKEN_ENCRYPTION_KEYS = {
    "v1": base64.urlsafe_b64encode(b"test-platform-token-encryption-key"[:32]).decode("ascii")
}
PLATFORM_MESSAGE_ENCRYPTION_ACTIVE_VERSION = "v1"
PLATFORM_MESSAGE_ENCRYPTION_KEYS = {
    "v1": base64.urlsafe_b64encode(b"test-platform-message-key-32-byte"[:32]).decode("ascii")
}
CRM_MESSAGE_ENCRYPTION_ACTIVE_VERSION = "v1"
CRM_MESSAGE_ENCRYPTION_KEYS = {
    "v1": base64.urlsafe_b64encode(b"test-crm-message-encryption-key-32!!!"[:32]).decode("ascii")
}