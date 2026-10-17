from uuid import UUID

from shared_kernel.ports import IAccountHealthChecker

from ...domain.events.backup_events import AccountHealthAlertRaised
from ..ports.backup_ports import IBackupClock, IBackupOutbox, IBackupUnitOfWork


class CheckAccountHealthUseCase:
    """Check one connection and enqueue an alert when provider health is not healthy.

    Contract: docs/15-use-cases-catalog.md#contexte-backup.
    """

    def __init__(
        self,
        health_checker: IAccountHealthChecker,
        unit_of_work: IBackupUnitOfWork,
        outbox: IBackupOutbox,
        clock: IBackupClock,
    ) -> None:
        """Receive the Platform Connectors health port and Backup Outbox boundary."""
        self._health_checker = health_checker
        self._unit_of_work = unit_of_work
        self._outbox = outbox
        self._clock = clock

    def execute(self, platform_connection_id: UUID) -> dict:
        """Return status/signals and persist an Outbox alert for at-risk connections."""
        status, signals = self._health_checker.check_account_status(platform_connection_id)
        if status != "healthy":
            with self._unit_of_work:
                self._outbox.add(
                    AccountHealthAlertRaised(
                        platform_connection_id=platform_connection_id,
                        health_status=status,
                        signals=tuple(signals),
                        occurred_at=self._clock.now_utc(),
                    )
                )
        return {"health_status": status, "signals": signals}