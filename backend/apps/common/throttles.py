"""Request throttles that do not accept client-controlled proxy headers."""

from rest_framework.throttling import ScopedRateThrottle


class RemoteAddressScopedRateThrottle(ScopedRateThrottle):
    """Use the socket peer for anonymous rate limits; ignore X-Forwarded-For.

    ``NUM_PROXIES`` is a deployment assertion, not proof that every caller is
    behind that proxy. Reading ``X-Forwarded-For`` here would let a caller that
    reaches the loopback-bound API port choose its own throttle identity.
    """

    extra_rates = {"public_snapshot": "120/minute"}

    def get_rate(self):
        return self.extra_rates.get(self.scope) or super().get_rate()

    def get_ident(self, request):
        return request.META.get("REMOTE_ADDR") or "unknown"
