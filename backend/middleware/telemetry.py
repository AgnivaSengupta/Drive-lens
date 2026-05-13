import time, logging
from starlette.middleware.base import BaseHTTPMiddleware

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("tailortalk")

class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = time.time()
        response = await call_next(request)
        duration = round((time.time() - start) * 1000, 2)
        logger.info(f"{request.method} {request.url.path} → {response.status_code} [{duration}ms]")
        return response