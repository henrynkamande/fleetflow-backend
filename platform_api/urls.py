from django.urls import path

from platform_api import views
from platform_api import views_auth

urlpatterns = [
    path('auth/register/', views_auth.platform_register, name='platform-auth-register'),
    path('auth/login/', views_auth.platform_login, name='platform-auth-login'),
    path('overview/', views.platform_overview, name='platform-overview'),
    path('companies/', views.platform_companies, name='platform-companies'),
    path('companies/<uuid:company_id>/', views.platform_company_detail, name='platform-company-detail'),
    path('users/', views.platform_users, name='platform-users'),
]
