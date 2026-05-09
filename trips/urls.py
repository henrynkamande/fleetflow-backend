# trips/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Trip CRUD
    path('', views.list_trips, name='list-trips'),
    path('create/', views.create_trip, name='create-trip'),
    path('<uuid:trip_id>/', views.get_trip, name='get-trip'),
    path('<uuid:trip_id>/update/', views.update_trip, name='update-trip'),
    
    # Trip Actions
    path('<uuid:trip_id>/start/', views.start_trip, name='start-trip'),
    path('<uuid:trip_id>/complete/', views.complete_trip, name='complete-trip'),
    path('<uuid:trip_id>/cancel/', views.cancel_trip, name='cancel-trip'),
    path('<uuid:trip_id>/approve/', views.approve_trip, name='approve-trip'),
]