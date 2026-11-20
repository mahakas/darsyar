from datetime import date, timedelta
from unittest import TestCase

from app.services.learning.flashcard_review import Recall, next_review


class FlashcardReviewTests(TestCase):
    def test_new_card_across_year_boundary(self) -> None:
        day = date(2026, 12, 31)
        for rating, due in ((Recall.AGAIN, 1), (Recall.HARD, 2), (Recall.EASY, 4)):
            with self.subTest(rating=rating):
                self.assertEqual(next_review(day, 0, rating), date(2027, 1, due))

    def test_repeated_success_then_lapse(self) -> None:
        day = date(2026, 11, 20)
        for previous, expected in ((4, 8), (8, 16), (64, 90), (90, 90)):
            self.assertEqual(next_review(day, previous, Recall.EASY), day + timedelta(days=expected))
        self.assertEqual(next_review(day, 90, Recall.HARD), day + timedelta(days=45))
        self.assertEqual(next_review(day, 90, Recall.AGAIN), day + timedelta(days=1))

    def test_every_valid_interval_respects_order_and_cap(self) -> None:
        day = date(2028, 2, 28)
        for previous in range(91):
            again, hard, easy = (next_review(day, previous, rating) for rating in Recall)
            self.assertTrue(day < again < hard < easy <= day + timedelta(days=90))

    def test_invalid_interval_rejected(self) -> None:
        for previous in (-1, 91):
            with self.assertRaises(ValueError):
                next_review(date(2026, 1, 1), previous, Recall.EASY)
