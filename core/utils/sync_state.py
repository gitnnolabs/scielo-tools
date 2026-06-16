from django.utils import timezone
from django.utils.dateparse import parse_datetime


def _normalize_datetime(value):
    if value is None:
        return None
    if hasattr(value, "utcoffset"):
        dt = value
    else:
        dt = parse_datetime(str(value))
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.utc)
    return dt


def track_max_from_item(current_max, item, field="updated"):
    """
    Retorna o timestamp mais recente encontrado ao iterar resultados da API.

    Converte ``item[field]`` e ``current_max`` para ``datetime`` antes de
    comparar, evitando erro ao misturar string ISO da API com ``DateTimeField``.

    Args:
        current_max: ``datetime`` já processado, ou None.
        item: Dicionário retornado pela API Core.
        field: Nome do campo de data em ``item`` (padrão: ``created``).

    Returns:
        O ``datetime`` mais recente entre ``current_max`` e ``item[field]``.
    """
    value = _normalize_datetime(item.get(field))
    current_max = _normalize_datetime(current_max)
    if value and (current_max is None or value > current_max):
        return value
    return current_max


def finalize_core_sync_state(sync_state, max_updated_at):
    """
    Persiste o checkpoint após uma execução bem-sucedida de sync da API Core.

    Args:
        sync_state: Instância de ``CoreSyncState`` do recurso sincronizado.
        max_updated_at: Maior ``created`` (ou equivalente) visto na execução.
    """
    sync_state.update_checkpoint(max_updated_at)
