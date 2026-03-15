import os
import sys
import unittest

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.utils.expense_parser import convert_words_to_numbers


class TestNumberParser(unittest.TestCase):
    """Regression tests for the current convert_words_to_numbers contract."""

    def test_numbers_without_multiplier_are_left_as_text_en(self):
        self.assertEqual(convert_words_to_numbers("one"), "one")
        self.assertEqual(convert_words_to_numbers("five"), "five")
        self.assertEqual(convert_words_to_numbers("ten"), "ten")
        self.assertEqual(convert_words_to_numbers("twenty one"), "twenty one")
        self.assertEqual(convert_words_to_numbers("one hundred"), "one hundred")
        self.assertEqual(convert_words_to_numbers("one hundred and fifty"), "one hundred and fifty")

    def test_numbers_without_multiplier_are_left_as_text_ru(self):
        self.assertEqual(convert_words_to_numbers("один"), "один")
        self.assertEqual(convert_words_to_numbers("пять"), "пять")
        self.assertEqual(convert_words_to_numbers("десять"), "десять")
        self.assertEqual(convert_words_to_numbers("двадцать один"), "двадцать один")
        self.assertEqual(convert_words_to_numbers("сто пятьдесят"), "сто пятьдесят")
        self.assertEqual(convert_words_to_numbers("трата сто пятьдесят на такси"), "трата сто пятьдесят на такси")

    def test_multiplier_phrases_are_converted_en(self):
        self.assertEqual(convert_words_to_numbers("thousand"), "1000")
        self.assertEqual(convert_words_to_numbers("million"), "1000000")
        self.assertEqual(convert_words_to_numbers("three thousand"), "3000")
        self.assertEqual(convert_words_to_numbers("twenty five thousand"), "25000")
        self.assertEqual(convert_words_to_numbers("one million"), "1000000")

    def test_multiplier_phrases_are_converted_ru(self):
        self.assertEqual(convert_words_to_numbers("тысяча"), "1000")
        self.assertEqual(convert_words_to_numbers("тысячи"), "1000")
        self.assertEqual(convert_words_to_numbers("тысяч"), "1000")
        self.assertEqual(convert_words_to_numbers("одна тысяча"), "1000")
        self.assertEqual(convert_words_to_numbers("две тысячи"), "2000")
        self.assertEqual(convert_words_to_numbers("пять тысяч"), "5000")
        self.assertEqual(
            convert_words_to_numbers("сто двадцать три тысячи четыреста пятьдесят шесть"),
            "123456",
        )

    def test_mixed_text_converts_only_multiplier_sequences(self):
        self.assertEqual(convert_words_to_numbers("salary five thousand dollars"), "salary 5000 dollars")
        self.assertEqual(convert_words_to_numbers("coffee two hundred"), "coffee two hundred")
        self.assertEqual(convert_words_to_numbers("купил молоко за пятьдесят рублей"), "купил молоко за пятьдесят рублей")

    def test_edge_cases_follow_current_normalization_rules(self):
        self.assertEqual(convert_words_to_numbers("Two Hundred"), "Two Hundred")
        self.assertEqual(convert_words_to_numbers("two hundred,"), "two hundred,")
        self.assertEqual(convert_words_to_numbers("forty-five"), "forty five")
        self.assertEqual(convert_words_to_numbers("hundred hundred"), "100 hundred hundred")


if __name__ == "__main__":
    unittest.main()
