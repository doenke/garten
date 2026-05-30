"""Static taxonomy resolver registrations."""

from ..registry import register_resolver
from .floraweb import FlorawebResolver
from .gbif import GbifResolver
from .mein_schoener_garten import MeinSchoenerGartenResolver
from .naturadb import NaturaDbResolver
from .passthrough import SearchQueryPassthroughResolver
from .powo import PowoResolver
from .wfo import WfoResolver


_REGISTERED_RESOLVERS = (
    GbifResolver(),
    PowoResolver(),
    WfoResolver(),
    FlorawebResolver(),
    NaturaDbResolver(),
    MeinSchoenerGartenResolver(),
    SearchQueryPassthroughResolver(),
)

for resolver in _REGISTERED_RESOLVERS:
    register_resolver(resolver)

__all__ = [
    'GbifResolver',
    'PowoResolver',
    'WfoResolver',
    'FlorawebResolver',
    'NaturaDbResolver',
    'MeinSchoenerGartenResolver',
    'SearchQueryPassthroughResolver',
]
