"""
Regression-тесты классификатора экранов арены на реальных failure
screenshots (план, Этап 1). Fixtures лежат в tests/fixtures/arena/ и
получены из debug/screenshots инцидента 2026-07-12.
"""
import unittest
from pathlib import Path

from PIL import Image

from locations.arena.screen_state import (
    ScreenState,
    ArenaScreenClassifier,
    classify_arena_screen,
)

FIXTURES_DIR = Path(__file__).parent / 'fixtures' / 'arena'

# button_locations Arena Classic (coordinates/arena_classic.json)
CLASSIC_BUTTONS = {1: [855, 205], 2: [855, 295], 3: [855, 380], 4: [855, 470]}


def pixel_getter_for(filename):
    image = Image.open(FIXTURES_DIR / filename).convert('RGB')
    return lambda x, y: image.getpixel((x, y))


class ArenaScreenClassifierTests(unittest.TestCase):
    def classify(self, filename):
        return classify_arena_screen(pixel_getter_for(filename), CLASSIC_BUTTONS)

    def test_fixture_15_54_44_is_exhausted_list_with_cooldown(self):
        """Скриншот 15-54-44: 2/10 жетонов, все видимые Victory, платный
        Refresh за рубины, free refresh через 11m 8s. Раньше этот экран
        превращался в UNKNOWN и запускал Escape-recovery."""
        observation = self.classify('classic_list_exhausted_cooldown.jpg')

        self.assertEqual(observation.state, ScreenState.ARENA_LIST_EXHAUSTED)
        self.assertIn('LIST_SHELL', observation.signals)
        self.assertIn('REFRESH_COOLDOWN', observation.signals)
        # Синяя доступная кнопка Refresh отсутствует: refresh платный.
        self.assertNotIn('REFRESH_AVAILABLE_FREE', observation.signals)

    def test_fixture_02_56_05_is_active_battle(self):
        """Скриншот 02-56-05: бой ещё идёт. Классификация ACTIVE_BATTLE
        запрещает continue-клики и Escape."""
        observation = self.classify('classic_active_battle.jpg')

        self.assertEqual(observation.state, ScreenState.ACTIVE_BATTLE)

    def test_fixture_02_12_39_is_result_reward(self):
        """Скриншот 02-12-39: экран награды с TAP TO CONTINUE."""
        observation = self.classify('classic_result_reward.jpg')

        self.assertEqual(observation.state, ScreenState.RESULT_REWARD)
        self.assertIn('TAP_TO_CONTINUE', observation.signals)

    def test_fixture_13_53_14_is_result_summary(self):
        """Скриншот 13-53-14: battle summary с RETURN TO ARENA."""
        observation = self.classify('classic_result_summary.jpg')

        self.assertEqual(observation.state, ScreenState.RESULT_SUMMARY)
        self.assertIn('RETURN_TO_ARENA', observation.signals)

    def test_fixture_13_35_31_is_result_summary(self):
        observation = self.classify('classic_result_summary_2.jpg')

        self.assertEqual(observation.state, ScreenState.RESULT_SUMMARY)

    def test_fixture_13_21_56_is_index_page(self):
        """Скриншот 13-21-56: бот выброшен на Index Page."""
        observation = self.classify('index_page.jpg')

        self.assertEqual(observation.state, ScreenState.INDEX)

    def test_no_fixture_is_misclassified_as_another_screen(self):
        """Каждый fixture должен распознаваться ровно одним состоянием,
        перекрёстных совпадений быть не должно."""
        expected = {
            'classic_list_exhausted_cooldown.jpg': ScreenState.ARENA_LIST_EXHAUSTED,
            'classic_active_battle.jpg': ScreenState.ACTIVE_BATTLE,
            'classic_result_reward.jpg': ScreenState.RESULT_REWARD,
            'classic_result_summary.jpg': ScreenState.RESULT_SUMMARY,
            'classic_result_summary_2.jpg': ScreenState.RESULT_SUMMARY,
            'index_page.jpg': ScreenState.INDEX,
        }
        for filename, state in expected.items():
            observation = self.classify(filename)
            self.assertEqual(
                observation.state,
                state,
                f"{filename}: expected {state.name}, got {observation.state.name}",
            )

    def test_active_battle_is_never_result(self):
        """Активный бой не должен получать result-клики (continue/Escape)."""
        observation = self.classify('classic_active_battle.jpg')

        self.assertNotIn(observation.state, [
            ScreenState.RESULT_REWARD,
            ScreenState.RESULT_SUMMARY,
        ])

    def test_stabilization_requires_consecutive_frames(self):
        classifier = ArenaScreenClassifier(
            pixel_getter_for('classic_active_battle.jpg'),
            CLASSIC_BUTTONS,
        )

        classifier.observe()
        self.assertFalse(classifier.is_stable(ScreenState.ACTIVE_BATTLE, frames=2))

        classifier.observe()
        self.assertTrue(classifier.is_stable(ScreenState.ACTIVE_BATTLE, frames=2))
        self.assertFalse(classifier.is_stable(ScreenState.UNKNOWN, frames=2))


if __name__ == '__main__':
    unittest.main()
