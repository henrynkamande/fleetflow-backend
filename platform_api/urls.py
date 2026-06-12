from django.urls import path

from platform_api import views
from platform_api import views_auth

urlpatterns = [
    path('auth/register/', views_auth.platform_register, name='platform-auth-register'),
    path('auth/login/', views_auth.platform_login, name='platform-auth-login'),
    path('overview/', views.platform_overview, name='platform-overview'),
    path('overview/signups/', views.platform_overview_signups, name='platform-overview-signups'),
    path('overview/activity/', views.platform_overview_activity, name='platform-overview-activity'),
    path('notifications/', views.platform_notifications, name='platform-notifications'),
    path('companies/', views.platform_companies, name='platform-companies'),
    path('companies/<uuid:company_id>/', views.platform_company_detail, name='platform-company-detail'),
    path('users/', views.platform_users, name='platform-users'),
    path('users/<uuid:user_id>/', views.platform_user_detail, name='platform-user-detail'),
    path('vehicles/', views.platform_vehicles, name='platform-vehicles'),
    path('vehicles/<uuid:vehicle_id>/', views.platform_vehicle_detail, name='platform-vehicle-detail'),
    path('subscriptions/', views.platform_subscriptions, name='platform-subscriptions'),
    path('system-expenses/', views.platform_system_expenses, name='platform-system-expenses'),
    path(
        'system-expenses/<uuid:expense_id>/',
        views.platform_system_expense_detail,
        name='platform-system-expense-detail',
    ),
]
