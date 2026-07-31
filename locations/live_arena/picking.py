def pop_next_character(pool, preferred_role=None):
    """Remove and return the next hero candidate without indexing an empty pool."""
    if not pool:
        return None

    index = 0
    if preferred_role is not None:
        for candidate_index, candidate in enumerate(pool):
            if candidate.get('role') == preferred_role:
                index = candidate_index
                break

    return pool.pop(index)
