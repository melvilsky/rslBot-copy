import unittest

from locations.live_arena.availability import (
    INDEX_INDICATOR_ACTIVE_LEGACY,
    INDEX_INDICATOR_ACTIVE_NEW,
    is_index_indicator_active,
)


class LiveArenaAvailabilityTests(unittest.TestCase):
    @staticmethod
    def checker_with_matches(*matching_indicators):
        matches = {repr(indicator) for indicator in matching_indicators}

        def check(indicator, mistake=0):
            return repr(indicator) in matches

        return check

    def test_legacy_indicator_still_marks_arena_active(self):
        checker = self.checker_with_matches(INDEX_INDICATOR_ACTIVE_LEGACY)

        self.assertTrue(is_index_indicator_active(checker))

    def test_both_new_indicator_pixels_mark_arena_active(self):
        checker = self.checker_with_matches(*INDEX_INDICATOR_ACTIVE_NEW)

        self.assertTrue(is_index_indicator_active(checker))

    def test_one_new_indicator_pixel_is_not_enough(self):
        for indicator in INDEX_INDICATOR_ACTIVE_NEW:
            with self.subTest(indicator=indicator):
                checker = self.checker_with_matches(indicator)
                self.assertFalse(is_index_indicator_active(checker))

    def test_no_indicator_marks_arena_inactive(self):
        self.assertFalse(is_index_indicator_active(self.checker_with_matches()))


if __name__ == '__main__':
    unittest.main()
