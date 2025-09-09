from django.urls import path
from . import views

app_name = 'panel'

urlpatterns = [
    # Главная страница - дашборд
    path('', views.dashboard, name='dashboard'),
    
    # Управление пользователями
    path('users/', views.users_list, name='users_list'),
    path('users/<int:user_id>/', views.user_detail, name='user_detail'),
    path('users/<int:user_id>/extend-subscription/', views.extend_subscription, name='extend_subscription'),
    path('users/<int:user_id>/send-message/', views.send_message, name='send_message'),
    
    # Рассылки
    path('broadcast/', views.broadcast_list, name='broadcast_list'),
    path('broadcast/create/', views.broadcast_create, name='broadcast_create'),
    path('broadcast/<int:broadcast_id>/', views.broadcast_detail, name='broadcast_detail'),
    
    # API endpoints для AJAX
    path('api/stats/', views.api_stats, name='api_stats'),
    path('api/users/search/', views.api_users_search, name='api_users_search'),

    # Партнёрская программа (кастомная админка)
    path('affiliate/', views.affiliate_dashboard, name='affiliate_dashboard'),
    path('affiliate/links/', views.affiliate_links, name='affiliate_links'),
    path('affiliate/referrals/', views.affiliate_referrals, name='affiliate_referrals'),
    path('affiliate/commissions/', views.affiliate_commissions, name='affiliate_commissions'),
]
