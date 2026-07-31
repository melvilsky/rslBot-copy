import unittest

from locations.live_arena.picking import pop_next_character


class LiveArenaPickingTests(unittest.TestCase):
    def test_prefers_matching_role_without_disturbing_other_candidates(self):
        pool = [
            {'name': 'Attacker', 'role': 'a'},
            {'name': 'Support', 'role': 's'},
        ]

        selected = pop_next_character(pool, preferred_role='s')

        self.assertEqual(selected['name'], 'Support')
        self.assertEqual([candidate['name'] for candidate in pool], ['Attacker'])

    def test_falls_back_to_next_candidate_when_preferred_role_is_exhausted(self):
        pool = [
            {'name': 'First fallback', 'role': 'a'},
            {'name': 'Second fallback', 'role': 'a'},
        ]

        selected = pop_next_character(pool, preferred_role='s')

        self.assertEqual(selected['name'], 'First fallback')
        self.assertEqual([candidate['name'] for candidate in pool], ['Second fallback'])

    def test_draining_pool_returns_none_instead_of_raising_index_error(self):
        pool = [{'name': 'Only candidate', 'role': 'a'}]

        self.assertEqual(
            pop_next_character(pool, preferred_role='s')['name'],
            'Only candidate',
        )
        self.assertIsNone(pop_next_character(pool, preferred_role='s'))


if __name__ == '__main__':
    unittest.main()
