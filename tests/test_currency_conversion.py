"""
Тесты для системы конвертации валют.
"""
import pytest
from decimal import Decimal
from datetime import date, timedelta
from unittest.mock import patch, AsyncMock, MagicMock


class TestFawazResponseParsing:
    """Тесты парсинга ответа Fawaz API"""

    def test_parse_fawaz_response_inversion(self):
        """
        Тест: Fawaz возвращает "1 RUB = X валюта", нужна инверсия!
        """
        from bot.services.currency_conversion import CurrencyConverter

        converter = CurrencyConverter()

        # Мок ответа Fawaz API: 1 RUB = 0.01 USD (т.е. 1 USD = 100 RUB)
        fawaz_response = {
            'date': '2026-02-03',
            'rub': {
                'usd': 0.01,     # 1 RUB = 0.01 USD → 1 USD = 100 RUB
                'eur': 0.0091,  # 1 RUB = 0.0091 EUR → 1 EUR = 109.89 RUB
                'ars': 10.0,    # 1 RUB = 10 ARS → 1 ARS = 0.1 RUB
            }
        }

        rates = converter._parse_fawaz_response(fawaz_response, 'rub')

        # Проверяем что курсы ИНВЕРТИРОВАНЫ
        assert 'USD' in rates
        usd_rate = float(rates['USD']['unit_rate'])
        assert abs(usd_rate - 100.0) < 0.1, f"USD rate should be ~100, got {usd_rate}"

        assert 'EUR' in rates
        eur_rate = float(rates['EUR']['unit_rate'])
        assert abs(eur_rate - 109.89) < 0.5, f"EUR rate should be ~109.89, got {eur_rate}"

        assert 'ARS' in rates
        ars_rate = float(rates['ARS']['unit_rate'])
        assert abs(ars_rate - 0.1) < 0.01, f"ARS rate should be ~0.1, got {ars_rate}"


class TestCBRFUnavailable:
    """Тесты для экзотических валют (недоступных в ЦБ РФ)"""

    def test_cbrf_unavailable_constant_exists(self):
        """Тест: константа CBRF_UNAVAILABLE существует"""
        from bot.services.currency_conversion import CurrencyConverter

        assert hasattr(CurrencyConverter, 'CBRF_UNAVAILABLE')
        assert 'ARS' in CurrencyConverter.CBRF_UNAVAILABLE
        assert 'COP' in CurrencyConverter.CBRF_UNAVAILABLE
        assert 'PEN' in CurrencyConverter.CBRF_UNAVAILABLE
        assert 'CLP' in CurrencyConverter.CBRF_UNAVAILABLE
        assert 'MXN' in CurrencyConverter.CBRF_UNAVAILABLE
        # USD и EUR НЕ должны быть в списке
        assert 'USD' not in CurrencyConverter.CBRF_UNAVAILABLE
        assert 'EUR' not in CurrencyConverter.CBRF_UNAVAILABLE


class TestConversionHelper:
    """Тесты для conversion_helper.py"""

    @pytest.mark.asyncio
    async def test_same_currency_no_conversion(self):
        """Тест: одинаковые валюты - без конвертации"""
        from bot.services.conversion_helper import maybe_convert_amount

        result = await maybe_convert_amount(
            amount=Decimal('100'),
            input_currency='RUB',
            user_currency='RUB',
            auto_convert_enabled=True
        )

        assert result[0] == Decimal('100')  # final_amount
        assert result[1] == 'RUB'  # final_currency
        assert result[2] is None  # original_amount
        assert result[3] is None  # original_currency
        assert result[4] is None  # exchange_rate

    @pytest.mark.asyncio
    async def test_auto_convert_disabled(self):
        """Тест: автоконвертация выключена - без конвертации"""
        from bot.services.conversion_helper import maybe_convert_amount

        result = await maybe_convert_amount(
            amount=Decimal('100'),
            input_currency='USD',
            user_currency='RUB',
            auto_convert_enabled=False  # Выключено!
        )

        assert result[0] == Decimal('100')
        assert result[1] == 'USD'  # Остаётся оригинальная валюта
        assert result[2] is None
        assert result[3] is None
        assert result[4] is None

    @pytest.mark.asyncio
    async def test_conversion_with_mock(self):
        """Тест: успешная конвертация с моком"""
        with patch('bot.services.conversion_helper.currency_converter') as mock:
            mock.convert_with_details = AsyncMock(
                return_value=(Decimal('9250'), Decimal('92.5'))
            )

            from bot.services.conversion_helper import maybe_convert_amount

            result = await maybe_convert_amount(
                amount=Decimal('100'),
                input_currency='USD',
                user_currency='RUB',
                auto_convert_enabled=True
            )

            assert result[0] == Decimal('9250')  # final_amount
            assert result[1] == 'RUB'  # final_currency
            assert result[2] == Decimal('100')  # original_amount
            assert result[3] == 'USD'  # original_currency
            assert result[4] == Decimal('92.5')  # exchange_rate

    @pytest.mark.asyncio
    async def test_graceful_degradation(self):
        """Тест: graceful degradation при ошибке конвертации"""
        with patch('bot.services.conversion_helper.currency_converter') as mock:
            mock.convert_with_details = AsyncMock(return_value=(None, None))

            from bot.services.conversion_helper import maybe_convert_amount

            result = await maybe_convert_amount(
                amount=Decimal('100'),
                input_currency='USD',
                user_currency='RUB',
                auto_convert_enabled=True
            )

            # При ошибке - сохраняем оригинал
            assert result[0] == Decimal('100')
            assert result[1] == 'USD'
            assert result[2] is None
            assert result[3] is None
            assert result[4] is None

    @pytest.mark.asyncio
    async def test_exotic_historical_no_conversion(self):
        """Тест: экзотика + прошлая дата = нет конвертации"""
        from bot.services.conversion_helper import maybe_convert_amount

        mock_profile = MagicMock()
        mock_profile.timezone = 'Europe/Moscow'

        yesterday = date.today() - timedelta(days=1)

        result = await maybe_convert_amount(
            amount=Decimal('100'),
            input_currency='ARS',  # Экзотика
            user_currency='RUB',
            auto_convert_enabled=True,
            operation_date=yesterday,  # Вчера
            profile=mock_profile
        )

        # Должен сохранить оригинал без конвертации
        assert result[0] == Decimal('100')
        assert result[1] == 'ARS'
        assert result[2] is None

    @pytest.mark.asyncio
    async def test_exotic_to_currency_check(self):
        """
        Тест: если to_currency экзотическая, тоже проверяем.
        Сценарий: from_currency=RUB, to_currency=ARS
        """
        from bot.services.conversion_helper import maybe_convert_amount

        mock_profile = MagicMock()
        mock_profile.timezone = 'Europe/Moscow'

        yesterday = date.today() - timedelta(days=1)

        result = await maybe_convert_amount(
            amount=Decimal('100'),
            input_currency='RUB',  # Не экзотика
            user_currency='ARS',   # Экзотика!
            auto_convert_enabled=True,
            operation_date=yesterday,
            profile=mock_profile
        )

        # Экзотика + история = graceful degradation
        assert result[0] == Decimal('100')
        assert result[1] == 'RUB'


class TestConvertWithDetails:
    """Тесты для метода convert_with_details"""

    @pytest.mark.asyncio
    async def test_same_currency_returns_one(self):
        """Тест: одинаковые валюты возвращают курс 1"""
        from bot.services.currency_conversion import currency_converter

        result = await currency_converter.convert_with_details(
            amount=Decimal('100'),
            from_currency='RUB',
            to_currency='RUB'
        )

        assert result[0] == Decimal('100')
        assert result[1] == Decimal('1')


class TestCacheKeys:
    """Тесты для ключей кеша"""

    def test_cache_key_includes_source(self):
        """Тест: ключ кеша включает источник"""
        from bot.services.currency_conversion import CurrencyConverter

        converter = CurrencyConverter()

        cbrf_key = converter._get_cache_key(date.today(), source='cbrf')
        fawaz_key = converter._get_cache_key(date.today(), source='fawaz')

        assert 'cbrf' in cbrf_key
        assert 'fawaz' in fawaz_key
        assert cbrf_key != fawaz_key
