"""Response compression middleware.

Django ships gzip support. Brotli needs an optional third-party package, so this
middleware only applies it when the `Brotli` package is available.
"""

try:
    from django.utils.cache import patch_vary_headers
except ImportError:  # pragma: no cover
    patch_vary_headers = None

try:
    import brotli
except ImportError:  # pragma: no cover - depends on deployment environment
    brotli = None


class BrotliMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if brotli is None:
            return response
        if 'br' not in request.META.get('HTTP_ACCEPT_ENCODING', ''):
            return response
        if response.streaming or response.has_header('Content-Encoding'):
            return response
        if response.status_code < 200 or response.status_code >= 300:
            return response
        if response.get('Content-Type', '').split(';', 1)[0] not in {
            'application/json',
            'text/html',
            'text/css',
            'text/javascript',
            'application/javascript',
        }:
            return response
        if len(response.content) < 1024:
            return response

        response.content = brotli.compress(response.content)
        response['Content-Encoding'] = 'br'
        response['Content-Length'] = str(len(response.content))
        if patch_vary_headers:
            patch_vary_headers(response, ('Accept-Encoding',))
        else:
            response['Vary'] = 'Accept-Encoding'
        return response
