import importlib
import os
import socket

import redis
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from piedlens_platform.event_bus.stream_consumer_worker import RedisStreamConsumerWorker


class Command(BaseCommand):
    help = "Run one configured Redis Streams consumer group."

    def add_arguments(self, parser):
        parser.add_argument("--stream", required=True)
        parser.add_argument("--context", required=True)
        parser.add_argument("--handler", required=True, help="Python dotted callable path")

    def handle(self, *args, **options):
        module_name, separator, attribute = options["handler"].rpartition(".")
        if not separator:
            raise CommandError("--handler must be a dotted Python callable path")
        try:
            handler = getattr(importlib.import_module(module_name), attribute)
        except (ImportError, AttributeError) as error:
            raise CommandError("Configured event handler could not be loaded") from error
        worker = RedisStreamConsumerWorker(
            redis.Redis.from_url(
                settings.REDIS_URL,
                decode_responses=False,
                **({"ssl_ca_certs": settings.REDIS_TLS_CA_CERTS} if settings.REDIS_TLS_CA_CERTS else {}),
            ),
            options["stream"],
            options["context"],
            os.environ.get("HOSTNAME", socket.gethostname()),
            handler,
            settings.STREAM_CLAIM_IDLE_MS,
            settings.STREAM_MAX_DELIVERIES,
        )
        worker.ensure_group()
        while True:
            worker.process_once()