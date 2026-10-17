import time

import redis
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from piedlens_platform.event_bus.outbox_models import OUTBOX_MODELS, outbox_model_for
from piedlens_platform.event_bus.outbox_relay_worker import OutboxRelayWorker
from piedlens_platform.event_bus.redis_stream_publisher import RedisStreamEventPublisher


class Command(BaseCommand):
    help = "Relay one bounded context Outbox to its Redis Stream."

    def add_arguments(self, parser):
        parser.add_argument("--context", required=True, choices=sorted(OUTBOX_MODELS))
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **options):
        context_name = options["context"]
        try:
            outbox_model = outbox_model_for(context_name)
        except (ImportError, ValueError) as error:
            raise CommandError(str(error)) from error
        client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=False,
            **({"ssl_ca_certs": settings.REDIS_TLS_CA_CERTS} if settings.REDIS_TLS_CA_CERTS else {}),
        )
        worker = OutboxRelayWorker(
            outbox_model,
            RedisStreamEventPublisher(client, f"{context_name}.events"),
            settings.OUTBOX_RELAY_BATCH_SIZE,
            settings.OUTBOX_RELAY_BACKOFF_BASE_SECONDS,
            settings.OUTBOX_RELAY_BACKOFF_MAX_SECONDS,
        )
        while True:
            count = worker.publish_batch()
            if options["once"]:
                self.stdout.write(str(count))
                return
            if count == 0:
                time.sleep(settings.OUTBOX_RELAY_POLL_INTERVAL_SECONDS)