"""CI settings keep PostgreSQL/Redis configuration while supplying test-only keyrings."""

import base64

from .settings import *


PLATFORM_TOKEN_ENCRYPTION_ACTIVE_VERSION = "v1"
PLATFORM_TOKEN_ENCRYPTION_KEYS = {
    "v1": base64.urlsafe_b64encode(b"ci-platform-token-key-material-32b"[:32]).decode("ascii")
}
PLATFORM_MESSAGE_ENCRYPTION_ACTIVE_VERSION = "v1"
PLATFORM_MESSAGE_ENCRYPTION_KEYS = {
    "v1": base64.urlsafe_b64encode(b"ci-platform-message-key-material"[:32]).decode("ascii")
}
BACKUP_DATA_ENCRYPTION_ACTIVE_VERSION = "v1"
BACKUP_DATA_ENCRYPTION_KEYS = {
    "v1": base64.urlsafe_b64encode(b"ci-backup-encryption-key-material!!"[:32]).decode("ascii")
}
CRM_MESSAGE_ENCRYPTION_ACTIVE_VERSION = "v1"
CRM_MESSAGE_ENCRYPTION_KEYS = {
    "v1": base64.urlsafe_b64encode(b"ci-crm-message-key-material-32bytes"[:32]).decode("ascii")
}