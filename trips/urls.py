# trips/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Trip CRUD
    path('', views.list_trips, name='list-trips'),
    path('create/', views.create_trip, name='create-trip'),
    path('<str:trip_ref>/update/', views.update_trip, name='update-trip'),
    path('<str:trip_ref>/delete/', views.delete_trip, name='delete-trip'),
    path('<str:trip_ref>/cancel/', views.cancel_trip, name='cancel-trip'),
    path('<uuid:trip_id>/start/', views.start_trip, name='start-trip'),
    path('<uuid:trip_id>/complete/', views.complete_trip, name='complete-trip'),
    path('<uuid:trip_id>/approve/', views.approve_trip, name='approve-trip'),
    path('<str:trip_ref>/', views.get_trip, name='get-trip'),
]