import unittest

from app.schemas import Signals
from app.scoring import score_lead


class ScoringTests(unittest.TestCase):
    def test_score_lead_marks_strong_distributor_signals_as_hot(self) -> None:
        signals = Signals(
            distributor_intent=True,
            commercial_intent=True,
            decision_maker=True,
            urgency="high",
            industry_relevance="high",
            geographic_scope="single_location",
            company_scale="large",
        )

        score, priority, classification, confidence = score_lead(signals)

        self.assertGreaterEqual(score, 70)
        self.assertEqual(priority, "Hot")
        self.assertEqual(classification, "Distributor")
        self.assertGreaterEqual(confidence, 0.75)


if __name__ == "__main__":
    unittest.main()
