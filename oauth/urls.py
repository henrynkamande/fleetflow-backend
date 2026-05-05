# urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Authentication
    path('auth/register/', views.register_fleet_owner, name='register-fleet-owner'),
    path('auth/login/', views.login, name='login'),
    path('auth/token/refresh/', views.refresh_token, name='token-refresh'),
    path('auth/logout/', views.logout, name='logout'),
    
    # OTP Management
    path('auth/resend-otp/', views.resend_driver_otp, name='resend-otp'),
    path('auth/verify-otp/', views.verify_driver_otp, name='verify-otp'),
    path('auth/check-temp-password/', views.check_temp_password_status, name='check-temp-password'),
    
    # Company management 
    path('company/register/', views.register_company, name='register-company'),
    path('company/', views.view_company, name='view-company'),
    path('company/update/', views.update_company, name='update-company'),
    path('company/status/', views.check_company_status, name='check-company-status'),
    
    # Driver onboarding
    path('drivers/onboard/', views.onboard_driver, name='onboard-driver'),
    
    # Profile
    path('profile/', views.view_profile, name='view-profile'),
    path('profile/update/', views.update_profile, name='update-profile'),
    path('profile/extended/', views.view_extended_profile, name='view-extended-profile'),
    path('profile/extended/update/', views.update_extended_profile, name='update-extended-profile'),
    
    # Password management
    path('password/change/', views.change_password, name='change-password'),
    path('password/forgot/', views.forgot_password, name='forgot-password'),
    path('password/reset/', views.reset_password, name='reset-password'),
    
    # User management (fleet owner only)
    path('users/', views.list_company_users, name='list-company-users'),
    path('users/<uuid:user_id>/', views.get_user_detail, name='get-user-detail'),
    path('users/<uuid:user_id>/deactivate/', views.deactivate_user, name='deactivate-user'),
    path('users/<uuid:user_id>/activate/', views.activate_user, name='activate-user'),
    
    # KYC documents
    path('kyc/', views.list_kyc_documents, name='list-kyc-documents'),
    path('kyc/upload/', views.upload_kyc_document, name='upload-kyc-document'),
    path('kyc/pending/', views.get_pending_kyc_documents, name='get-pending-kyc-documents'),
    path('kyc/expired/', views.get_expired_kyc_documents, name='get-expired-kyc-documents'),
    path('kyc/<uuid:document_id>/', views.get_kyc_document, name='get-kyc-document'),
    path('kyc/<uuid:document_id>/update/', views.update_kyc_document, name='update-kyc-document'),
    path('kyc/<uuid:document_id>/delete/', views.delete_kyc_document, name='delete-kyc-document'),
    path('kyc/<uuid:document_id>/verify/', views.verify_kyc_document, name='verify-kyc-document'),
    
    # Dashboards
    path('dashboard/fleet-owner/', views.fleet_owner_dashboard, name='fleet-owner-dashboard'),
    path('dashboard/driver/', views.driver_dashboard, name='driver-dashboard'),
]