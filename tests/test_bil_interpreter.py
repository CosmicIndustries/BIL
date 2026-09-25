"""Test suite for bil_v07_interpreter.py.

None existed before this file (see CLAUDE.md). Two kinds of tests live here:

- Regression tests for behavior that currently works, pinning it so future
  changes don't silently break it.
- Invariant tests for the three properties TOKEN_REGISTRY is supposed to
  hold (injective, delimiter-free, total) and related dictionary-consistency
  checks. These are marked @unittest.expectedFailure because the invariants
  are currently violated -- see CLAUDE.md for the specifics. If one of these
  starts passing, unittest reports it as an "unexpected success": that's the
  signal to remove the expectedFailure marker and lock the fix in.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bil_v07_interpreter as bil


class TokenRegistryInvariantTests(unittest.TestCase):
    @unittest.expectedFailure
    def test_delimiter_free(self):
        """No token may contain the C1/C2 slot-delimiter symbols as its own content."""
        colliding = {
            concept: token
            for concept, token in bil.TOKEN_REGISTRY.items()
            if "C1" in token.split() or "C2" in token.split()
        }
        self.assertEqual(colliding, {})

    @unittest.expectedFailure
    def test_total(self):
        """Every concept SUES_MAP can produce must have a TOKEN_REGISTRY entry."""
        concepts = set(bil.SUES_MAP.values())
        missing = concepts - set(bil.TOKEN_REGISTRY.keys())
        self.assertEqual(missing, set())

    @unittest.expectedFailure
    def test_injective(self):
        """Each token string must map back to exactly one concept."""
        tokens = list(bil.TOKEN_REGISTRY.values())
        dupes = {t for t in tokens if tokens.count(t) > 1}
        self.assertEqual(dupes, set())


class DictionaryConsistencyTests(unittest.TestCase):
    @unittest.expectedFailure
    def test_english_to_sues_targets_exist(self):
        """Every ENGLISH_TO_SUES value must be a real SUES_MAP key."""
        orphans = set(bil.ENGLISH_TO_SUES.values()) - set(bil.SUES_MAP.keys())
        self.assertEqual(orphans, set())


class EncodeDecodeCollisionTests(unittest.TestCase):
    @unittest.expectedFailure
    def test_c1_collision_corrupts_slot_boundaries(self):
        """Pins the delimiter collision documented in CLAUDE.md.

        Note: the token stream is currently write-only (no decoder exists in
        the module), so this collision breaks nothing *today*. It demonstrates
        that the stream is non-decodable by construction, which blocks any
        future decoder: speech.act.say encodes to "W1 C1 R1" -- its own C1
        collides with the slot separator encode_bil_ir uses, so splitting the
        encoded stream on " C1 " does not recover the original two tokens.
        """
        bil_ir = {
            "speech_act": "speech.act.say",
            "semantic_frame": {"agent": "entity.person.speaker"},
        }
        encoded = bil.encode_bil_ir(bil_ir)
        body = encoded.rsplit(" C2", 1)[0]
        slots = body.split(" C1 ")
        self.assertEqual(slots, ["W1 C1 R1", "R1 W1"])


class AmbiguityResolverTests(unittest.TestCase):
    def test_run_program_resolves_to_system_operate(self):
        result = bil.resolve_ambiguous_word("run", ["run", "program"])
        self.assertEqual(result["chosen_sues"], "sysdo")

    def test_run_store_resolves_to_motion(self):
        result = bil.resolve_ambiguous_word("run", ["run", "store"])
        self.assertEqual(result["chosen_sues"], "faststep")

    def test_bank_loan_resolves_to_financial_institution(self):
        result = bil.resolve_ambiguous_word("bank", ["bank", "loan"])
        self.assertEqual(result["chosen_sues"], "moneyhouse")

    def test_bank_river_resolves_to_riverbank(self):
        result = bil.resolve_ambiguous_word("bank", ["river", "bank"])
        self.assertEqual(result["chosen_sues"], "riveredge")

    def test_light_bright_resolves_to_illumination(self):
        result = bil.resolve_ambiguous_word("light", ["light", "bright"])
        self.assertEqual(result["chosen_sues"], "seeenergy")

    def test_light_carry_resolves_to_lightweight(self):
        result = bil.resolve_ambiguous_word("light", ["light", "carry"])
        self.assertEqual(result["chosen_sues"], "weight-")

    def test_unambiguous_word_short_circuits(self):
        result = bil.resolve_ambiguous_word("build", ["build", "system"])
        self.assertFalse(result["ambiguous"])
        self.assertEqual(result["confidence"], 1.0)

    def test_no_clue_match_yields_zero_confidence(self):
        result = bil.resolve_ambiguous_word("run", ["run"])
        self.assertTrue(result["ambiguous"])
        self.assertIsNone(result["chosen_sues"])
        self.assertEqual(result["confidence"], 0.0)


class SuesSlotParsingTests(unittest.TestCase):
    def test_map_sues_term_passes_through_unknown_terms(self):
        self.assertEqual(bil.map_sues_term("not_a_real_term"), "not_a_real_term")

    def test_map_sues_term_resolves_known_terms(self):
        self.assertEqual(bil.map_sues_term("@self"), "entity.person.speaker")

    def test_parse_sues_slots_splits_stacked_style(self):
        slots = bil.parse_sues_slots("STYLE:stepclear+technical")
        self.assertEqual(
            slots["STYLE"],
            ["style.structure.step_by_step", "style.register.technical"],
        )

    def test_normalize_english_strips_punctuation_and_lowercases(self):
        self.assertEqual(bil.normalize_english("Fix the code."), ["fix", "the", "code"])


class ValidateBilIrTests(unittest.TestCase):
    def test_missing_predicate_is_an_error(self):
        result = bil.validate_bil_ir({"speech_act": "speech.act.say", "semantic_frame": {}})
        self.assertFalse(result["valid"])
        self.assertIn("Missing semantic_frame.predicate", result["errors"])

    def test_complete_frame_is_valid(self):
        result = bil.validate_bil_ir(
            {
                "speech_act": "speech.act.command",
                "semantic_frame": {
                    "agent": "entity.person.addressee",
                    "predicate": "action.repair.restore_function",
                    "object": "object.software.code",
                },
            }
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["errors"], [])


class N8nHandleTests(unittest.TestCase):
    def test_missing_input_text_is_rejected(self):
        result = bil.n8n_handle({"thread_id": "t", "input_type": "english", "input_text": ""})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "Missing input_text")

    def test_unsupported_input_type_is_rejected(self):
        result = bil.n8n_handle({"thread_id": "t", "input_type": "klingon", "input_text": "hi"})
        self.assertFalse(result["ok"])
        self.assertIn("Unsupported input_type", result["error"])

    def test_valid_english_input_returns_full_contract(self):
        result = bil.n8n_handle(
            {"thread_id": "t", "input_type": "english", "input_text": "Fix the code."}
        )
        self.assertTrue(result["ok"])
        for key in ("bil_ir", "validation", "bil_tokens", "output_text"):
            self.assertIn(key, result)


class DemoRoundtripTests(unittest.TestCase):
    """Pins the current pass/fail state of each README demo case.

    README claims 7/8 pass, with "The light is bright." failing because
    adjective predicates have no predicate-slot mapping yet. If that gap
    gets fixed, update the expected value below rather than deleting it --
    the point is to notice the behavior changed, not just that it did.
    """

    EXPECTED_OK = {
        "Please build the system.": True,
        "Fix the code.": True,
        "Run the program.": True,
        "Run to the store.": True,
        "The bank approved the loan.": True,
        "Sit by the river bank.": True,
        "Set the value to 10.": True,
        "The light is bright.": False,
    }

    def test_demo_cases_match_expected_validity(self):
        self.assertEqual(set(self.EXPECTED_OK), set(bil._DEMO_CASES))
        for case in bil._DEMO_CASES:
            with self.subTest(case=case):
                result = bil.roundtrip_test(case)
                self.assertEqual(result["ok"], self.EXPECTED_OK[case])


if __name__ == "__main__":
    unittest.main()
