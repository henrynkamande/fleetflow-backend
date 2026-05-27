from django.urls import path

from . import views

urlpatterns = [
    path('config/', views.billing_config, name='billing-config'),
    path('status/', views.billing_status, name='billing-status'),
    path('checkout-session/', views.create_checkout_session, name='billing-checkout-session'),
    path('confirm-checkout/', views.confirm_checkout, name='billing-confirm-checkout'),
    path('portal-session/', views.create_portal_session, name='billing-portal-session'),
    path('webhook/', views.stripe_webhook, name='stripe-webhook'),
]
