"""App-wide config values. Tunable knobs live here."""
from __future__ import annotations

# Nudge strength for the preference-vector update:
#   preference_vector = (1 - BETA) * preference_vector + BETA * item_embedding
# Small enough that one like doesn't hijack the profile, big enough that
# ~5-10 likes noticeably shift recommendations.
BETA: float = 0.15

# Default number of recommendations returned by GET /profiles/{id}/recommendations.
DEFAULT_REC_LIMIT: int = 20

# Max allowed limit clients can request.
MAX_REC_LIMIT: int = 100
