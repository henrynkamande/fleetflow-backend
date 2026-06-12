from django.urls import path

from . import views


urlpatterns = [
    path('', views.list_expenses, name='list-expenses'),
    path('create/', views.create_expense, name='create-expense'),
    path('<uuid:expense_id>/', views.expense_detail, name='expense-detail'),
]
