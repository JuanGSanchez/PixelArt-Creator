"""Tests for ``pixelart_creator.logic.language_names`` (Qt-free).

Covers ``REQ-L10N-UI-003``: the language selector names every language by its
own name, in one fixed order, whatever language the interface is in.
"""

from __future__ import annotations

import itertools

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic import language_names

# Copied from the requirement's list, in its order: English, Espanol, Francais,
# Deutsch, Russian, Simplified Chinese, Japanese, Korean. Each label is given as
# the UTF-8 bytes of the requirement's text, so the test compares bytes and not
# whatever a source editor or a font made of the characters.
EXPECTED = (
    ("en", b"English"),
    ("es", b"Espa\xc3\xb1ol"),
    ("fr", b"Fran\xc3\xa7ais"),
    ("de", b"Deutsch"),
    ("ru", b"\xd0\xa0\xd1\x83\xd1\x81\xd1\x81\xd0\xba\xd0\xb8\xd0\xb9"),
    ("zh_CN", b"\xe7\xae\x80\xe4\xbd\x93\xe4\xb8\xad\xe6\x96\x87"),
    ("ja", b"\xe6\x97\xa5\xe6\x9c\xac\xe8\xaa\x9e"),
    ("ko", b"\xed\x95\x9c\xea\xb5\xad\xec\x96\xb4"),
)
CODES = tuple(code for code, _ in EXPECTED)


class TestEndonymBytes:
    """The eight labels are byte-exact to the requirement.

    This class is the evidence for the reading of the constitution's Article V.2
    that a language's own name is data and not translatable text: the labels are
    fixed strings compared as UTF-8 bytes, identical in every interface language,
    with no ``tr()`` involved. A one-byte change to any endonym fails it.
    """

    @pytest.mark.parametrize(("code", "literal"), EXPECTED)
    def test_endonym_is_byte_exact(self, code, literal):
        """Compare each endonym, encoded as UTF-8, with the requirement's bytes."""
        assert language_names.ENDONYMS[code].encode("utf-8") == literal

    def test_table_holds_exactly_the_eight_languages(self):
        """Hold no code beyond the eight shipped ones."""
        assert set(language_names.ENDONYMS) == set(CODES)

    def test_no_label_is_its_raw_code(self):
        """Never show a raw code as a label."""
        for code, label in language_names.ENDONYMS.items():
            assert label != code

    def test_table_is_read_only(self):
        """Refuse an assignment to the shared table."""
        with pytest.raises(TypeError):
            language_names.ENDONYMS["en"] = "English!"


class TestSelectorOrder:
    """The selector order is the requirement's order."""

    def test_order_is_the_requirements_order(self):
        """List the codes in the order the requirement fixes."""
        assert language_names.SELECTOR_ORDER == CODES

    def test_order_has_no_duplicates(self):
        """Name each code once."""
        order = language_names.SELECTOR_ORDER
        assert len(set(order)) == len(order)


class TestSelectorEntries:
    """``selector_entries`` pairs each shipped code with its endonym, in order."""

    def test_all_languages_give_the_full_ordered_table(self):
        """Return all eight pairs, byte-exact, in the requirement's order."""
        entries = language_names.selector_entries(set(CODES))
        assert [(c, label.encode("utf-8")) for c, label in entries] == list(EXPECTED)

    @pytest.mark.parametrize("order", [CODES, CODES[::-1], tuple(sorted(CODES))])
    def test_input_order_does_not_change_the_result(self, order):
        """Order the entries by the selector order, not by the input order."""
        full = language_names.selector_entries(CODES)
        assert language_names.selector_entries(order) == full

    def test_subset_keeps_selector_order(self):
        """Leave out an absent language and keep the rest in order."""
        entries = language_names.selector_entries(["ko", "en", "zh_CN"])
        assert [code for code, _ in entries] == ["en", "zh_CN", "ko"]

    def test_empty_available_gives_no_entries(self):
        """Return no entries for no languages."""
        assert language_names.selector_entries([]) == ()

    def test_returns_a_tuple_of_pairs(self):
        """Return an immutable tuple of two-item tuples."""
        entries = language_names.selector_entries(["en"])
        assert entries == (("en", "English"),)

    def test_unknown_code_raises(self):
        """Raise rather than let a raw code reach the menu."""
        with pytest.raises(language_names.UnknownLanguageError):
            language_names.selector_entries([*CODES, "pt_BR"])

    def test_error_names_every_unknown_code_sorted(self):
        """Name each missing code, sorted, in the message."""
        with pytest.raises(language_names.UnknownLanguageError) as info:
            language_names.selector_entries(["en", "xx", "aa"])
        assert str(info.value).endswith("aa, xx")

    def test_unknown_code_error_is_a_value_error(self):
        """Keep the error catchable as a ValueError."""
        assert issubclass(language_names.UnknownLanguageError, ValueError)

    @given(st.sets(st.sampled_from(CODES)))
    def test_any_subset_is_ordered_and_complete(self, subset):
        """Keep exactly the subset's codes, in selector order."""
        entries = language_names.selector_entries(subset)
        expected = [code for code in language_names.SELECTOR_ORDER if code in subset]
        assert [code for code, _ in entries] == expected

    @given(st.permutations(CODES))
    def test_any_permutation_gives_the_same_entries(self, permutation):
        """Give the same entries for every ordering of the full set."""
        full = language_names.selector_entries(CODES)
        assert language_names.selector_entries(permutation) == full

    def test_every_pair_of_labels_differs(self):
        """Give each language a label no other language shares."""
        labels = [label for _, label in language_names.selector_entries(CODES)]
        for first, second in itertools.combinations(labels, 2):
            assert first != second
