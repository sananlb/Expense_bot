import asyncio
import logging
import aiohttp
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, List, Tuple
from django.core.cache import cache

logger = logging.getLogger(__name__)


class CurrencyConverter:
    """Currency conversion service using multiple API sources with fallback support"""

    # Primary API (Free, no limits)
    FAWAZ_API_URL = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies"

    # Валюты НЕ доступные через ЦБ РФ (только Fawaz)
    CBRF_UNAVAILABLE = {'ARS', 'COP', 'PEN', 'CLP', 'MXN'}
    
    # Fallback APIs
    CBRF_DAILY_URL = "http://www.cbr.ru/scripts/XML_daily.asp"
    CBRF_DYNAMIC_URL = "http://www.cbr.ru/scripts/XML_dynamic.asp"
    
    # Popular currencies with their CBRF IDs (for fallback)
    CBRF_CURRENCY_CODES = {
        'USD': 'R01235',  # US Dollar
        'EUR': 'R01239',  # Euro
        'CNY': 'R01375',  # Chinese Yuan
        'GBP': 'R01035',  # British Pound
        'JPY': 'R01820',  # Japanese Yen
        'TRY': 'R01700J', # Turkish Lira
        'KZT': 'R01335',  # Kazakh Tenge
        'BYN': 'R01815',  # Belarusian Ruble
        'UAH': 'R01720',  # Ukrainian Hryvnia
        'CHF': 'R01775',  # Swiss Franc
    }
    
    # Supported currencies (all currencies supported by primary API)
    SUPPORTED_CURRENCIES = {
        # Latin American currencies
        'ARS': 'Argentine Peso',
        'COP': 'Colombian Peso', 
        'PEN': 'Peruvian Sol',
        'CLP': 'Chilean Peso',
        'MXN': 'Mexican Peso',
        'BRL': 'Brazilian Real',
        'UYU': 'Uruguayan Peso',
        'BOB': 'Bolivian Boliviano',
        'CRC': 'Costa Rican Colón',
        'GTQ': 'Guatemalan Quetzal',
        'HNL': 'Honduran Lempira',
        'NIO': 'Nicaraguan Córdoba',
        'PAB': 'Panamanian Balboa',
        'PYG': 'Paraguayan Guaraní',
        'DOP': 'Dominican Peso',
        'JMD': 'Jamaican Dollar',
        'TTD': 'Trinidad and Tobago Dollar',
        'BBD': 'Barbadian Dollar',
        'BSD': 'Bahamian Dollar',
        'BZD': 'Belize Dollar',
        'XCD': 'East Caribbean Dollar',
        
        # Middle East currencies
        'AED': 'UAE Dirham',

        # CIS and nearby currencies
        'INR': 'Indian Rupee',
        'UZS': 'Uzbek Som',
        'AMD': 'Armenian Dram',
        'TMT': 'Turkmenistan Manat',
        'AZN': 'Azerbaijani Manat',
        'KGS': 'Kyrgyz Som',
        'TJS': 'Tajik Somoni',
        'MDL': 'Moldovan Leu',
        'GEL': 'Georgian Lari',

        # Major world currencies
        'USD': 'US Dollar',
        'EUR': 'Euro',
        'CNY': 'Chinese Yuan',
        'GBP': 'British Pound',
        'JPY': 'Japanese Yen',
        'TRY': 'Turkish Lira',
        'KZT': 'Kazakh Tenge',
        'BYN': 'Belarusian Ruble',
        'UAH': 'Ukrainian Hryvnia',
        'CHF': 'Swiss Franc',
        'RUB': 'Russian Ruble',
    }
    
    def __init__(self):
        self.session = None
        self._cache_prefix = "currency_rate"
        self._cache_timeout = 3600 * 24  # 24 hours
    
    async def _ensure_session(self):
        """Ensure aiohttp session exists and is usable.

        Handles the case where session was created in a different event loop
        (e.g. when called from Celery via async_to_sync, which creates and
        destroys event loops between invocations).

        Checks three conditions in order:
        1. session.closed — session was explicitly closed
        2. connector.closed — connector lost its transport layer
        3. loop mismatch — session was created in a different (possibly dead) event loop
        """
        if self.session is not None:
            stale = False
            if self.session.closed:
                stale = True
            elif self.session.connector is not None and self.session.connector.closed:
                stale = True
            else:
                # aiohttp stores the loop reference on the connector;
                # if the original loop is closed or differs from the running one,
                # any I/O on the session will raise "Event loop is closed".
                try:
                    running_loop = asyncio.get_running_loop()
                    connector = self.session.connector
                    session_loop = getattr(connector, '_loop', None)
                    if session_loop is not None and session_loop is not running_loop:
                        stale = True
                    elif session_loop is not None and session_loop.is_closed():
                        stale = True
                except RuntimeError:
                    # No running loop — session is unusable anyway
                    stale = True
            if stale:
                # Best-effort close to free resources; ignore errors on dead loop
                try:
                    await self.session.close()
                except Exception:
                    pass
                self.session = None
        if self.session is None:
            self.session = aiohttp.ClientSession()
    
    async def fetch_fawaz_rates(self, base_currency: str = 'rub') -> Dict[str, Dict]:
        """
        Fetch exchange rates from Fawaz API
        
        Returns dict: {
            'USD': {'value': 75.5, 'nominal': 1, 'name': 'US Dollar'},
            'EUR': {'value': 89.2, 'nominal': 1, 'name': 'Euro'},
            ...
        }
        """
        await self._ensure_session()
        
        # Check cache first
        cache_key = f"fawaz_rates:{base_currency.lower()}:{date.today().isoformat()}"
        cached_rates = cache.get(cache_key)
        if cached_rates:
            return cached_rates
        
        try:
            url = f"{self.FAWAZ_API_URL}/{base_currency.lower()}.json"
            async with self.session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    logger.error(f"Fawaz API error: {response.status}")
                    return {}
                
                data = await response.json()
                rates = self._parse_fawaz_response(data, base_currency)
                
                # Cache the results
                cache.set(cache_key, rates, self._cache_timeout)
                
                return rates
                
        except Exception as e:
            logger.error(f"Error fetching Fawaz rates: {e}")
            return {}

    def _parse_fawaz_response(self, data: dict, base_currency: str) -> Dict[str, Dict]:
        """
        Parse Fawaz API response

        ВАЖНО: Fawaz возвращает курс "1 RUB = X USD" (например 0.01),
        но нам нужен курс "1 USD = X RUB" (например 100).
        Поэтому мы ИНВЕРТИРУЕМ курс.
        """
        try:
            rates = {}
            currency_data = data.get(base_currency.lower(), {})

            for currency_code, rate_value in currency_data.items():
                if currency_code.upper() in self.SUPPORTED_CURRENCIES:
                    currency_upper = currency_code.upper()

                    # КРИТИЧНО: Инвертируем курс!
                    # Fawaz: "1 RUB = 0.01 USD" -> Нам нужно: "1 USD = 100 RUB"
                    if rate_value and rate_value > 0:
                        inverted_rate = Decimal('1') / Decimal(str(rate_value))
                    else:
                        continue

                    rates[currency_upper] = {
                        'value': inverted_rate,
                        'nominal': 1,
                        'name': self.SUPPORTED_CURRENCIES.get(currency_upper, currency_upper),
                        'unit_rate': inverted_rate  # 1 USD = ~100 RUB
                    }

            return rates

        except Exception as e:
            logger.error(f"Error parsing Fawaz response: {e}")
            return {}

    async def fetch_daily_rates(self, date_obj: Optional[date] = None,
                                from_currency: Optional[str] = None,
                                to_currency: Optional[str] = None) -> Dict[str, Dict]:
        """
        Fetch daily exchange rates.

        Strategy:
        - CBRF (ЦБ РФ) is PRIMARY for standard currencies (USD, EUR, CNY, etc.)
        - Fawaz is used ONLY for exotic currencies (ARS, COP, PEN, CLP, MXN)
        - Fawaz is FALLBACK if CBRF fails for standard currencies

        Args:
            date_obj: Date for exchange rate (default: today)
            from_currency: Source currency code for source selection
            to_currency: Target currency code for source selection

        Returns dict: {
            'USD': {'value': 75.5, 'nominal': 1, 'name': 'US Dollar'},
            'EUR': {'value': 89.2, 'nominal': 1, 'name': 'Euro'},
            ...
        }
        """
        await self._ensure_session()

        # Determine if we need Fawaz API (exotic currencies not available in CBRF)
        needs_fawaz = False
        if from_currency and from_currency.upper() in self.CBRF_UNAVAILABLE:
            needs_fawaz = True
        if to_currency and to_currency.upper() in self.CBRF_UNAVAILABLE:
            needs_fawaz = True

        # Determine source for cache key
        source = 'fawaz' if needs_fawaz else 'cbrf'

        # Check cache first
        cache_key = self._get_cache_key(date_obj, source)
        cached_rates = cache.get(cache_key)
        if cached_rates:
            return cached_rates

        # If exotic currency needed, use Fawaz API only
        if needs_fawaz:
            if not date_obj or date_obj == date.today():
                rates = await self.fetch_fawaz_rates('rub')
                if rates:
                    logger.info("Successfully fetched rates from Fawaz API (exotic currency)")
                    cache.set(cache_key, rates, self._cache_timeout)
                    return rates
            # Fawaz doesn't support historical data for exotic currencies
            logger.warning(f"Cannot fetch historical rates for exotic currencies")
            return {}

        # PRIMARY: CBRF (ЦБ РФ) for standard currencies
        rates = await self.fetch_cbrf_rates(date_obj)
        if rates:
            logger.info(f"Successfully fetched {len(rates)} rates from CBRF")
            cache.set(cache_key, rates, self._cache_timeout)
            return rates

        # FALLBACK: Fawaz if CBRF fails (only for today, Fawaz has no historical data)
        if not date_obj or date_obj == date.today():
            logger.warning("CBRF unavailable, falling back to Fawaz API")
            fawaz_cache_key = self._get_cache_key(date_obj, 'fawaz_fallback')
            rates = await self.fetch_fawaz_rates('rub')
            if rates:
                logger.info("Successfully fetched rates from Fawaz API (fallback)")
                cache.set(fawaz_cache_key, rates, self._cache_timeout)
                return rates

        logger.error(f"Failed to fetch rates from any source for date {date_obj}")
        return {}

    async def fetch_cbrf_rates(self, date_obj: Optional[date] = None) -> Dict[str, Dict]:
        """
        Fetch daily exchange rates from CBRF (original implementation)
        """
        # Format date for CBRF API
        if date_obj:
            date_str = date_obj.strftime('%d/%m/%Y')
            params = {'date_req': date_str}
        else:
            params = {}
        
        try:
            async with self.session.get(
                self.CBRF_DAILY_URL,
                params=params,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    logger.error(f"CBRF API error: {response.status}")
                    return {}
                
                content = await response.text()
                rates = self._parse_daily_xml(content)
                
                return rates
                
        except Exception as e:
            logger.error(f"Error fetching CBRF rates: {e}")
            return {}
    
    def _parse_daily_xml(self, xml_content: str) -> Dict[str, Dict]:
        """Parse CBRF XML response"""
        try:
            root = ET.fromstring(xml_content)
            rates = {}
            
            for valute in root.findall('.//Valute'):
                char_code = valute.find('CharCode').text
                nominal = int(valute.find('Nominal').text)
                name = valute.find('Name').text
                value = valute.find('Value').text.replace(',', '.')
                
                rates[char_code] = {
                    'value': Decimal(value),
                    'nominal': nominal,
                    'name': name,
                    'unit_rate': Decimal(value) / nominal
                }
            
            return rates
            
        except Exception as e:
            logger.error(f"Error parsing CBRF XML: {e}")
            return {}
    
    async def convert(self, amount: Decimal, from_currency: str, 
                     to_currency: str = 'RUB', 
                     conversion_date: Optional[date] = None) -> Optional[Decimal]:
        """
        Convert amount between currencies
        
        Args:
            amount: Amount to convert
            from_currency: Source currency code (e.g., 'USD')
            to_currency: Target currency code (default 'RUB')
            conversion_date: Date for exchange rate (default: today)
        
        Returns:
            Converted amount or None if conversion failed
        """
        # Приводим amount к Decimal если пришёл float/int
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))

        if from_currency == to_currency:
            return amount

        if not conversion_date:
            conversion_date = date.today()
        
        # Handle weekends - use Friday's rate
        if conversion_date.weekday() in [5, 6]:  # Saturday or Sunday
            days_back = conversion_date.weekday() - 4
            conversion_date = conversion_date - timedelta(days=days_back)
        
        # Get rates (pass currencies for proper source selection)
        rates = await self.fetch_daily_rates(
            conversion_date,
            from_currency=from_currency,
            to_currency=to_currency
        )
        if not rates:
            # Try previous business day
            conversion_date = self._get_previous_business_day(conversion_date)
            rates = await self.fetch_daily_rates(
                conversion_date,
                from_currency=from_currency,
                to_currency=to_currency
            )
            if not rates:
                logger.error(f"No rates available for {conversion_date}")
                return None
        
        # Convert to RUB first
        if from_currency == 'RUB':
            rub_amount = amount
        else:
            if from_currency not in rates:
                logger.error(f"Currency {from_currency} not found in rates")
                return None
            rub_amount = amount * rates[from_currency]['unit_rate']
        
        # Convert from RUB to target currency
        if to_currency == 'RUB':
            return rub_amount
        else:
            if to_currency not in rates:
                logger.error(f"Currency {to_currency} not found in rates")
                return None
            return rub_amount / rates[to_currency]['unit_rate']
    
    async def get_rate(self, currency_code: str,
                      rate_date: Optional[date] = None) -> Optional[Decimal]:
        """Get exchange rate for specific currency (relative to RUB)"""
        # Pass currency_code for proper source selection (exotic currencies use Fawaz)
        rates = await self.fetch_daily_rates(
            rate_date,
            from_currency=currency_code,
            to_currency='RUB'
        )
        if currency_code in rates:
            return rates[currency_code]['unit_rate']
        return None

    async def convert_with_details(
        self,
        amount: Decimal,
        from_currency: str,
        to_currency: str = 'RUB',
        conversion_date: Optional[date] = None
    ) -> Tuple[Optional[Decimal], Optional[Decimal]]:
        """
        Конвертирует сумму и возвращает использованный курс.

        Args:
            amount: Amount to convert
            from_currency: Source currency code (e.g., 'USD')
            to_currency: Target currency code (default 'RUB')
            conversion_date: Date for exchange rate (default: today)

        Returns:
            (converted_amount, rate_used) или (None, None) при ошибке
        """
        # Приводим amount к Decimal если пришёл float/int
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))

        if from_currency == to_currency:
            return amount, Decimal('1')

        if not conversion_date:
            conversion_date = date.today()

        rates = await self.fetch_daily_rates(
            conversion_date,
            from_currency=from_currency,
            to_currency=to_currency
        )
        if not rates:
            logger.warning(f"No rates available for conversion {from_currency} -> {to_currency} on {conversion_date}")
            return None, None

        # Конвертация
        if from_currency == 'RUB':
            if to_currency not in rates:
                logger.warning(f"Currency {to_currency} not found in rates for date {conversion_date}")
                return None, None
            rate = Decimal('1') / rates[to_currency]['unit_rate']
            result = (amount * rate).quantize(Decimal('0.01'))
            logger.info(f"Converted {amount} {from_currency} -> {result} {to_currency} (rate: {rate:.6f}, date: {conversion_date})")
            return result, rate

        if to_currency == 'RUB':
            if from_currency not in rates:
                logger.warning(f"Currency {from_currency} not found in rates for date {conversion_date}")
                return None, None
            rate = rates[from_currency]['unit_rate']
            result = (amount * rate).quantize(Decimal('0.01'))
            logger.info(f"Converted {amount} {from_currency} -> {result} {to_currency} (rate: {rate:.6f}, date: {conversion_date})")
            return result, rate

        # Кросс-курс через RUB
        if from_currency not in rates or to_currency not in rates:
            logger.warning(f"Cross-rate conversion failed: {from_currency} or {to_currency} not in rates for {conversion_date}")
            return None, None

        from_rate = rates[from_currency]['unit_rate']
        to_rate = rates[to_currency]['unit_rate']
        rate = from_rate / to_rate
        result = (amount * rate).quantize(Decimal('0.01'))
        logger.info(f"Cross-converted {amount} {from_currency} -> {result} {to_currency} (rate: {rate:.6f}, date: {conversion_date})")
        return result, rate
    
    async def get_available_currencies(self) -> List[Tuple[str, str]]:
        """Get list of available currencies"""
        # Return all supported currencies from our comprehensive list
        return [(code, name) for code, name in self.SUPPORTED_CURRENCIES.items()]
    
    async def get_live_currency_rates(self) -> Dict[str, Decimal]:
        """Get current exchange rates for all supported currencies"""
        rates = await self.fetch_daily_rates()
        return {code: info['unit_rate'] for code, info in rates.items()}
    
    def _get_cache_key(self, date_obj: Optional[date] = None, source: str = 'cbrf') -> str:
        """Generate cache key for rates WITH source prefix"""
        if not date_obj:
            date_obj = date.today()
        return f"{self._cache_prefix}:{source}:{date_obj.isoformat()}"
    
    def _get_previous_business_day(self, date_obj: date) -> date:
        """Get previous business day (Mon-Fri)"""
        prev_day = date_obj - timedelta(days=1)
        while prev_day.weekday() in [5, 6]:  # Skip weekends
            prev_day -= timedelta(days=1)
        return prev_day
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.session:
            await self.session.close()


# Singleton instance
currency_converter = CurrencyConverter()


async def convert_currency(amount: Decimal, from_currency: str, 
                          to_currency: str = 'RUB',
                          conversion_date: Optional[date] = None) -> Optional[Decimal]:
    """Helper function for easy currency conversion"""
    return await currency_converter.convert(
        amount, from_currency, to_currency, conversion_date
    )


async def get_exchange_rate(currency_code: str, 
                           rate_date: Optional[date] = None) -> Optional[Decimal]:
    """Helper function to get exchange rate"""
    return await currency_converter.get_rate(currency_code, rate_date)