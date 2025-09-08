"""
Health check and monitoring views for expense_bot
"""
import logging
import time
import asyncio
from datetime import datetime, timedelta
from django.http import JsonResponse
from django.views import View
from django.utils import timezone
from django.db import connection
from django.core.cache import cache
from django.conf import settings
import redis
from .models import SystemHealthCheck, AIServiceMetrics, UserAnalytics, Profile

logger = logging.getLogger(__name__)


class HealthCheckView(View):
    """
    Health check endpoint для мониторинга состояния системы
    """
    
    def get(self, request):
        """
        Выполняет проверку здоровья всех компонентов системы
        
        Returns:
            JsonResponse с статусом системы и метриками
        """
        start_time = time.time()
        health_data = {
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'checks': {},
            'metrics': {}
        }
        
        # 1. Проверка базы данных
        db_start = time.time()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
            db_response_time = time.time() - db_start
            health_data['checks']['database'] = {
                'status': 'ok',
                'response_time': db_response_time
            }
            database_status = True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            db_response_time = None
            health_data['checks']['database'] = {
                'status': 'error',
                'error': str(e)
            }
            health_data['status'] = 'unhealthy'
            database_status = False
        
        # 2. Проверка Redis
        redis_start = time.time()
        try:
            r = redis.Redis(
                host=settings.REDIS_HOST if hasattr(settings, 'REDIS_HOST') else 'localhost',
                port=int(settings.REDIS_PORT if hasattr(settings, 'REDIS_PORT') else 6379),
                db=0,
                socket_connect_timeout=2
            )
            r.ping()
            redis_response_time = time.time() - redis_start
            health_data['checks']['redis'] = {
                'status': 'ok',
                'response_time': redis_response_time
            }
            redis_status = True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            redis_response_time = None
            health_data['checks']['redis'] = {
                'status': 'error',
                'error': str(e)
            }
            health_data['status'] = 'degraded'
            redis_status = False
        
        # 3. Проверка кэша Django
        cache_start = time.time()
        try:
            cache.set('health_check', 'ok', 10)
            value = cache.get('health_check')
            if value == 'ok':
                health_data['checks']['cache'] = {
                    'status': 'ok',
                    'response_time': time.time() - cache_start
                }
                cache_status = True
            else:
                raise ValueError("Cache test failed")
        except Exception as e:
            logger.error(f"Cache health check failed: {e}")
            health_data['checks']['cache'] = {
                'status': 'error',
                'error': str(e)
            }
            health_data['status'] = 'degraded'
            cache_status = False
        
        # 4. Проверка AI сервисов (последние метрики)
        try:
            # Получаем последние метрики AI за последний час
            one_hour_ago = timezone.now() - timedelta(hours=1)
            ai_metrics = AIServiceMetrics.objects.filter(
                timestamp__gte=one_hour_ago
            ).values('service').distinct()
            
            ai_services_status = {}
            for service in ['openai', 'google']:
                service_metrics = AIServiceMetrics.objects.filter(
                    service=service,
                    timestamp__gte=one_hour_ago
                ).order_by('-timestamp').first()
                
                if service_metrics:
                    # Вычисляем средний response time и success rate
                    last_hour_metrics = AIServiceMetrics.objects.filter(
                        service=service,
                        timestamp__gte=one_hour_ago
                    )
                    total_calls = last_hour_metrics.count()
                    successful_calls = last_hour_metrics.filter(success=True).count()
                    avg_response_time = last_hour_metrics.filter(
                        success=True
                    ).values_list('response_time', flat=True)
                    
                    if avg_response_time:
                        avg_time = sum(avg_response_time) / len(avg_response_time)
                    else:
                        avg_time = 0
                    
                    success_rate = (successful_calls / total_calls * 100) if total_calls > 0 else 0
                    
                    ai_services_status[service] = {
                        'status': 'ok' if success_rate > 80 else 'degraded',
                        'success_rate': f"{success_rate:.1f}%",
                        'avg_response_time': f"{avg_time:.2f}s",
                        'total_calls': total_calls
                    }
                else:
                    ai_services_status[service] = {
                        'status': 'unknown',
                        'message': 'No recent metrics'
                    }
            
            health_data['checks']['ai_services'] = ai_services_status
            ai_status = all(s.get('status') != 'error' for s in ai_services_status.values())
        except Exception as e:
            logger.error(f"AI services health check failed: {e}")
            health_data['checks']['ai_services'] = {
                'status': 'error',
                'error': str(e)
            }
            ai_status = False
        
        # 5. Собираем общие метрики системы
        try:
            # Активные пользователи за последние 24 часа
            yesterday = timezone.now() - timedelta(days=1)
            active_users = UserAnalytics.objects.filter(
                date__gte=yesterday.date()
            ).values('profile').distinct().count()
            
            # Общее количество пользователей
            total_users = Profile.objects.filter(is_active=True).count()
            
            # Количество обработанных сообщений за последний час
            recent_analytics = UserAnalytics.objects.filter(
                date=timezone.now().date()
            ).values_list('messages_sent', flat=True)
            total_messages_today = sum(recent_analytics)
            
            health_data['metrics'] = {
                'active_users_24h': active_users,
                'total_users': total_users,
                'messages_today': total_messages_today,
                'uptime': self._get_uptime()
            }
        except Exception as e:
            logger.warning(f"Failed to collect system metrics: {e}")
        
        # 6. Сохраняем результат проверки в БД
        try:
            # Определяем статус AI сервисов (с проверкой на None)
            ai_services_status = ai_services_status or {}
            openai_status = ai_services_status.get('openai', {}).get('status', 'unknown') == 'ok'
            google_status = ai_services_status.get('google', {}).get('status', 'unknown') == 'ok'
            
            # Формируем список проблем
            issues = []
            if not database_status:
                issues.append("Database is down")
            if not redis_status:
                issues.append("Redis is down")
            if not cache_status:
                issues.append("Cache is not working")
            if not openai_status:
                issues.append("OpenAI API issues")
            if not google_status:
                issues.append("Google AI API issues")
            
            # Определяем общий статус
            overall_status = 'healthy' if not issues else ('unhealthy' if len(issues) > 2 else 'degraded')
            
            SystemHealthCheck.objects.create(
                database_status=database_status,
                database_response_time=db_response_time,
                redis_status=redis_status,
                redis_response_time=redis_response_time,
                telegram_api_status=True,  # Если endpoint отвечает, значит Django работает
                openai_api_status=openai_status,
                google_ai_api_status=google_status,
                celery_status=True,  # TODO: implement actual celery check
                overall_status=overall_status,
                issues=issues
            )
        except Exception as e:
            logger.error(f"Failed to save health check result: {e}")
        
        # Определяем общий статус
        health_data['response_time'] = f"{time.time() - start_time:.3f}s"
        
        # Возвращаем результат с соответствующим HTTP кодом
        status_code = 200 if health_data['status'] == 'healthy' else \
                      503 if health_data['status'] == 'unhealthy' else 206
        
        return JsonResponse(health_data, status=status_code)
    
    def _get_uptime(self):
        """
        Получает uptime процесса
        """
        try:
            import psutil
            import os
            process = psutil.Process(os.getpid())
            create_time = datetime.fromtimestamp(process.create_time())
            uptime = datetime.now() - create_time
            return str(uptime).split('.')[0]  # Убираем микросекунды
        except ImportError:
            # psutil не установлен, пробуем альтернативный метод
            try:
                import os
                import time
                # Используем время запуска Django
                startup_time = getattr(settings, 'STARTUP_TIME', None)
                if startup_time:
                    uptime = datetime.now() - startup_time
                    return str(uptime).split('.')[0]
                else:
                    return "unknown"
            except:
                return "unknown"
        except Exception:
            return "unknown"


class MetricsView(View):
    """
    Endpoint для получения детальных метрик системы
    """
    
    def get(self, request):
        """
        Возвращает детальные метрики системы за указанный период
        """
        # Параметры запроса
        period = request.GET.get('period', '1h')  # 1h, 24h, 7d, 30d
        
        # Определяем временной диапазон
        now = timezone.now()
        if period == '1h':
            start_time = now - timedelta(hours=1)
        elif period == '24h':
            start_time = now - timedelta(days=1)
        elif period == '7d':
            start_time = now - timedelta(days=7)
        elif period == '30d':
            start_time = now - timedelta(days=30)
        else:
            start_time = now - timedelta(hours=1)
        
        metrics = {
            'period': period,
            'timestamp': now.isoformat(),
            'ai_services': {},
            'user_activity': {},
            'system_health': {}
        }
        
        # AI сервисы метрики
        try:
            for service in ['openai', 'google']:
                service_metrics = AIServiceMetrics.objects.filter(
                    service=service,
                    timestamp__gte=start_time
                )
                
                total = service_metrics.count()
                successful = service_metrics.filter(success=True).count()
                
                if total > 0:
                    response_times = service_metrics.filter(
                        success=True
                    ).values_list('response_time', flat=True)
                    
                    metrics['ai_services'][service] = {
                        'total_requests': total,
                        'successful_requests': successful,
                        'failed_requests': total - successful,
                        'success_rate': f"{(successful/total*100):.1f}%",
                        'avg_response_time': f"{sum(response_times)/len(response_times):.2f}s" if response_times else "0s",
                        'min_response_time': f"{min(response_times):.2f}s" if response_times else "0s",
                        'max_response_time': f"{max(response_times):.2f}s" if response_times else "0s"
                    }
        except Exception as e:
            logger.error(f"Failed to collect AI metrics: {e}")
        
        # Активность пользователей
        try:
            if period in ['1h', '24h']:
                # Для коротких периодов берем данные за сегодня
                analytics = UserAnalytics.objects.filter(
                    date=timezone.now().date()
                )
            else:
                # Для длинных периодов берем данные за период
                analytics = UserAnalytics.objects.filter(
                    date__gte=start_time.date()
                )
            
            if analytics.exists():
                metrics['user_activity'] = {
                    'active_users': analytics.values('profile').distinct().count(),
                    'total_messages': sum(analytics.values_list('messages_sent', flat=True)),
                    'total_expenses': sum(analytics.values_list('expenses_added', flat=True)),
                    'ai_requests': sum(analytics.values_list('ai_requests', flat=True))
                }
        except Exception as e:
            logger.error(f"Failed to collect user activity metrics: {e}")
        
        # История проверок системы
        try:
            health_checks = SystemHealthCheck.objects.filter(
                timestamp__gte=start_time
            ).order_by('-timestamp')[:10]
            
            if health_checks:
                successful_checks = health_checks.filter(
                    database_status=True,
                    redis_status=True
                ).count()
                
                metrics['system_health'] = {
                    'total_checks': health_checks.count(),
                    'successful_checks': successful_checks,
                    'availability': f"{(successful_checks/health_checks.count()*100):.1f}%",
                    'last_check': health_checks[0].timestamp.isoformat() if health_checks else None
                }
        except Exception as e:
            logger.error(f"Failed to collect system health metrics: {e}")
        
        return JsonResponse(metrics)