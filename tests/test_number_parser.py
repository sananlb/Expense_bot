import sys
import os
import unittest

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.utils.expense_parser import convert_words_to_numbers

class TestNumberParser(unittest.TestCase):
    def test_simple_numbers_en(self):
        self.assertEqual(convert_words_to_numbers("one"), "1")
        self.assertEqual(convert_words_to_numbers("five"), "5")
        self.assertEqual(convert_words_to_numbers("ten"), "10")
        self.assertEqual(convert_words_to_numbers("zero"), "0")

    def test_simple_numbers_ru(self):
        self.assertEqual(convert_words_to_numbers("один"), "1")
        self.assertEqual(convert_words_to_numbers("пять"), "5")
        self.assertEqual(convert_words_to_numbers("десять"), "10")
        self.assertEqual(convert_words_to_numbers("ноль"), "0")

    def test_composite_numbers_en(self):
        self.assertEqual(convert_words_to_numbers("twenty one"), "21")
        self.assertEqual(convert_words_to_numbers("forty-five"), "45")
        self.assertEqual(convert_words_to_numbers("one hundred"), "100")
        self.assertEqual(convert_words_to_numbers("two hundred"), "200")
        self.assertEqual(convert_words_to_numbers("one hundred fifty"), "150")
        self.assertEqual(convert_words_to_numbers("three thousand"), "3000")
        self.assertEqual(convert_words_to_numbers("twenty five thousand"), "25000")
        self.assertEqual(convert_words_to_numbers("one million"), "1000000")

    def test_composite_numbers_ru(self):
        self.assertEqual(convert_words_to_numbers("двадцать один"), "21")
        self.assertEqual(convert_words_to_numbers("сто пятьдесят"), "150")
        self.assertEqual(convert_words_to_numbers("двести"), "200")
        self.assertEqual(convert_words_to_numbers("пятьсот"), "500")
        self.assertEqual(convert_words_to_numbers("одна тысяча"), "1000")
        self.assertEqual(convert_words_to_numbers("две тысячи"), "2000")
        self.assertEqual(convert_words_to_numbers("пять тысяч"), "5000")
        self.assertEqual(convert_words_to_numbers("сто двадцать три тысячи четыреста пятьдесят шесть"), "123456")

    def test_mixed_text(self):
        self.assertEqual(convert_words_to_numbers("coffee two hundred"), "coffee 200")
        self.assertEqual(convert_words_to_numbers("salary five thousand dollars"), "salary 5000 dollars")
        self.assertEqual(convert_words_to_numbers("купил молоко за пятьдесят рублей"), "купил молоко за 50 рублей")
        self.assertEqual(convert_words_to_numbers("трата сто пятьдесят на такси"), "трата 150 на такси")

    def test_edge_cases(self):
        # Case insensitivity
        self.assertEqual(convert_words_to_numbers("Two Hundred"), "200")
        # Punctuation
        self.assertEqual(convert_words_to_numbers("two hundred,"), "200,")
        # "And" in English
        self.assertEqual(convert_words_to_numbers("one hundred and fifty"), "150")
        # Negative
        self.assertEqual(convert_words_to_numbers("minus five"), "-5")
        self.assertEqual(convert_words_to_numbers("минус пять"), "-5")
        
    def test_invalid_sequences(self):
        # Should parse what it can or leave as is, but not crash
        # "hundred hundred" -> 100 100 (ideally) or just text
        # Current implementation might be tricky, let's see what we want.
        # Ideally: "hundred" alone is 100. "hundred hundred" -> "100 100"
        self.assertEqual(convert_words_to_numbers("hundred hundred"), "100 100")
        
    def test_declensions_ru(self):
        self.assertEqual(convert_words_to_numbers("двух"), "2")
        self.assertEqual(convert_words_to_numbers("пяти"), "5")
        self.assertEqual(convert_words_to_numbers("тысячи"), "1000")
        self.assertEqual(convert_words_to_numbers("тысяч"), "1000")

if __name__ == '__main__':
    unittest.main()
