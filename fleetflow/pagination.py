"""Shared limit/offset pagination for function-based list views."""

from django.core.paginator import Paginator

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20


def parse_page_params(request, *, default_page_size: int = DEFAULT_PAGE_SIZE) -> tuple[int, int]:
    page = max(1, int(request.query_params.get('page', 1)))
    raw_size = request.query_params.get('page_size', request.query_params.get('limit', default_page_size))
    try:
        page_size = int(raw_size)
    except (TypeError, ValueError):
        page_size = default_page_size
    page_size = min(MAX_PAGE_SIZE, max(1, page_size))
    return page, page_size


def paginate_queryset(request, queryset, *, default_page_size: int = DEFAULT_PAGE_SIZE):
    """
    Slice queryset for the requested page. Returns (page_obj, meta dict).
    meta includes count, page, page_size, total_pages.
    """
    page, page_size = parse_page_params(request, default_page_size=default_page_size)
    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(page)
    meta = {
        'count': paginator.count,
        'page': page,
        'page_size': page_size,
        'total_pages': paginator.num_pages,
    }
    return page_obj, meta
