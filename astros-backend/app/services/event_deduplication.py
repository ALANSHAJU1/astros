from typing import TypeVar

T = TypeVar("T")


def deduplicate_events(events: list[T]) -> list[T]:
    """Deduplicate events, preferring the record with the latest end time."""

    unique: dict[tuple, T] = {}

    for event in events:
        external_id = getattr(event, "external_event_id", None)

        # Don't merge records without a stable external identifier.
        if not external_id:
            key = ("database_id", str(getattr(event, "id", id(event))))
        else:
            key = (
                external_id,
                getattr(event, "category", None),
                getattr(event, "event_type", None),
                getattr(event, "start_time", None),
            )

        existing = unique.get(key)

        if existing is None:
            unique[key] = event
            continue

        existing_end = getattr(existing, "end_time", None)
        candidate_end = getattr(event, "end_time", None)

        if (
            candidate_end is not None
            and (existing_end is None or candidate_end > existing_end)
        ):
            unique[key] = event

    return list(unique.values())
