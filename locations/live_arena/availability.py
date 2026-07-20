INDEX_INDICATOR_ACTIVE_LEGACY = [822, 474, [62, 170, 53]]

# New Live Arena tile layout: both pixels identify the active state together.
INDEX_INDICATOR_ACTIVE_NEW = [
    [748, 475, [184, 92, 255]],
    [836, 473, [52, 166, 49]],
]

INDEX_INDICATOR_MISTAKE = 10


def is_index_indicator_active(pixel_checker):
    """Return True when either the legacy or the new active layout is visible."""
    if pixel_checker(
        INDEX_INDICATOR_ACTIVE_LEGACY,
        mistake=INDEX_INDICATOR_MISTAKE,
    ):
        return True

    return all(
        pixel_checker(indicator, mistake=INDEX_INDICATOR_MISTAKE)
        for indicator in INDEX_INDICATOR_ACTIVE_NEW
    )
