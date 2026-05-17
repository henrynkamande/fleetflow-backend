from django.urls import path

from . import views

urlpatterns = [
    path('overview/', views.finance_overview, name='finance-overview'),
    path('income/', views.finance_income, name='finance-income'),
    path('expenses/', views.finance_expenses, name='finance-expenses'),
    path('pl/', views.finance_pl, name='finance-pl'),
]
