"""Tests for the voice command parser."""

from __future__ import annotations

from app.speech.commands import CommandType, VoiceCommandParser, parse_number


def _flat(parts):
    return [
        (part.command.command, part.command.argument) if part.command else part.text
        for part in parts
    ]


class TestParseNumber:
    def test_digits(self) -> None:
        assert parse_number(["15"]) == (15, 1)

    def test_urdu_digits(self) -> None:
        assert parse_number(["۱۵"]) == (15, 1)

    def test_compound_english(self) -> None:
        assert parse_number(["one", "hundred", "twenty", "five"]) == (125, 4)

    def test_roman_urdu(self) -> None:
        assert parse_number(["bees"]) == (20, 1)

    def test_not_a_number(self) -> None:
        assert parse_number(["hello"]) == (None, 0)


class TestVoiceCommandParser:
    def setup_method(self) -> None:
        self.parser = VoiceCommandParser()

    def test_plain_dictation(self) -> None:
        parts = self.parser.parse("this is normal dictated text")
        assert _flat(parts) == ["this is normal dictated text"]

    def test_command_then_text(self) -> None:
        parts = self.parser.parse("heading introduction")
        assert _flat(parts) == [(CommandType.HEADING, None), "introduction"]

    def test_subheading_beats_heading(self) -> None:
        parts = self.parser.parse("sub heading details")
        assert _flat(parts)[0] == (CommandType.SUBHEADING, None)

    def test_mixed_stream(self) -> None:
        parts = self.parser.parse(
            "heading agreement new paragraph the parties agree bold strongly"
        )
        assert _flat(parts) == [
            (CommandType.HEADING, None),
            "agreement",
            (CommandType.NEW_PARAGRAPH, None),
            "the parties agree",
            (CommandType.BOLD, None),
            "strongly",
        ]

    def test_go_to_page_digits(self) -> None:
        assert _flat(self.parser.parse("go to page 15")) == [
            (CommandType.GO_TO_PAGE, 15)
        ]

    def test_go_to_page_words(self) -> None:
        assert _flat(self.parser.parse("go to page fifteen")) == [
            (CommandType.GO_TO_PAGE, 15)
        ]

    def test_navigation(self) -> None:
        assert _flat(self.parser.parse("next page")) == [(CommandType.NEXT_PAGE, None)]
        assert _flat(self.parser.parse("previous page")) == [
            (CommandType.PREVIOUS_PAGE, None)
        ]

    def test_roman_urdu_commands(self) -> None:
        assert _flat(self.parser.parse("naya paragraph")) == [
            (CommandType.NEW_PARAGRAPH, None)
        ]
        assert _flat(self.parser.parse("agla safha")) == [
            (CommandType.NEXT_PAGE, None)
        ]

    def test_urdu_script_go_to_page(self) -> None:
        assert _flat(self.parser.parse("صفحہ نمبر بیس")) == [
            (CommandType.GO_TO_PAGE, 20)
        ]

    def test_page_break(self) -> None:
        assert _flat(self.parser.parse("insert page break")) == [
            (CommandType.PAGE_BREAK, None)
        ]
