from django.http import JsonResponse

# Must match `content.urls` admin cover upload path (without trailing slash variance).
_BLOG_COVER_UPLOAD_PATH = '/content/api/admin/uploads/cover/'
_MAX_BYTES = 5 * 1024 * 1024  # 5 MB


class BlogCoverUploadMiddleware:
    """
    Reject invalid blog cover uploads before the view parses large bodies.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path.rstrip('/')
        if request.method == 'POST' and path == _BLOG_COVER_UPLOAD_PATH.rstrip('/'):
            content_type = (request.META.get('CONTENT_TYPE') or '').lower()
            if not content_type.startswith('multipart/form-data'):
                return JsonResponse(
                    {'detail': 'Cover upload must use multipart/form-data.'},
                    status=415,
                )

            content_length = request.META.get('CONTENT_LENGTH')
            if content_length:
                try:
                    if int(content_length) > _MAX_BYTES:
                        return JsonResponse(
                            {
                                'detail': (
                                    f'Cover image must be {_MAX_BYTES // (1024 * 1024)} MB or smaller.'
                                ),
                            },
                            status=413,
                        )
                except (TypeError, ValueError):
                    return JsonResponse(
                        {'detail': 'Invalid Content-Length header.'},
                        status=400,
                    )

        return self.get_response(request)
