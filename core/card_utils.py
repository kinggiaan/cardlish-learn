"""
Shared utilities for card pipeline scripts.

Centralizes common logic like card number parsing to avoid
inconsistencies across scripts.
"""

import re
from typing import Optional, Set, List


def parse_card_filter(cards_str: Optional[str], all_pair_ids: List[str] = None) -> Optional[Set[str]]:
    """Parse --cards argument into a set of pair_ids.

    Matches both '{num}_card' format (from PDF pipeline) and bare '{num}' format
    (from photo import) to prevent silent mismatches.

    Args:
        cards_str: Comma-separated card numbers or pair_ids (e.g. "1,2,3" or "015_card")
        all_pair_ids: Optional list of all known pair_ids to match against.
                      If provided, fuzzy-matches bare numbers to actual pair_ids.

    Returns:
        Set of pair_ids to match, or None if no filter specified.
    """
    if not cards_str:
        return None

    result = set()
    for part in cards_str.split(","):
        part = part.strip()
        if not part:
            continue

        # If it already contains '_' or alpha chars (not just digits), use as-is
        if "_" in part or not part.isdigit():
            result.add(part)
        else:
            # Bare number: generate both possible formats
            padded = f"{int(part):03d}"
            result.add(f"{padded}_card")  # Primary: 015_card
            result.add(padded)             # Fallback: 015 (legacy photo import)

    # If we have access to all pair_ids, filter to only existing ones
    if all_pair_ids is not None:
        known = set(all_pair_ids)
        result = result & known

    return result if result else None
