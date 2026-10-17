from uuid import UUID

from ..exceptions import InvalidConfirmationTokenException
from ..ports.backup_ports import (
    IBackupClock,
    IBackupOutbox,
    IBackupRepository,
    IBackupUnitOfWork,
    IConfirmationTokenVerifier,
    IObjectStorage,
)
from ...domain.events.backup_events import MerchantDataDeleted


class DeleteAllMerchantDataUseCase:
    """Purge Backup-owned data only after merchant-bound double confirmation (INV-BK-04).

    Contract: docs/15-use-cases-catalog.md#contexte-backup.
    Emits a transactional deletion event so each other context purges only its own data.
    """

    def __init__(
        self,
        backups: IBackupRepository,
        storage: IObjectStorage,
        token_verifier: IConfirmationTokenVerifier,
        unit_of_work: IBackupUnitOfWork,
        outbox: IBackupOutbox,
        clock: IBackupClock,
    ) -> None:
        """Receive Backup-owned repositories, token verification, transaction and clock."""
        self._backups = backups
        self._storage = storage
        self._token_verifier = token_verifier
        self._unit_of_work = unit_of_work
        self._outbox = outbox
        self._clock = clock

    def execute(self, merchant_id: UUID, confirmation_token: str) -> dict:
        """Delete Backup data and publish MerchantDataDeleted only for a valid second token."""
        if not self._token_verifier.is_valid(merchant_id, confirmation_token):
            raise InvalidConfirmationTokenException("A valid deletion confirmation is required.")
        deleted_at = self._clock.now_utc()
        with self._unit_of_work:
            references = self._backups.delete_for_merchant(merchant_id)
            for reference in references:
                self._storage.delete(reference)
            self._outbox.add(MerchantDataDeleted(merchant_id, deleted_at))
        return {"deleted_at": deleted_at}