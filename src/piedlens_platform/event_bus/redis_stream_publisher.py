"""Module: piedlens_platform/event_bus/redis_stream_publisher.py
Context: transverse platform layer, consumed by bounded contexts.
Role: Redis Streams publisher placeholder behind IEventPublisher.

This module must only be invoked by an outbox relay. A Use Case must never
publish directly to Redis; persist each event in its producer outbox instead.
See docs/14-event-driven-architecture.md and invariant INV-TR-02.
"""