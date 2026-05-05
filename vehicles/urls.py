# vehicles/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Vehicle CRUD
    path('', views.list_vehicles, name='list-vehicles'),
    path('create/', views.create_vehicle, name='create-vehicle'),
    path('<uuid:vehicle_id>/', views.get_vehicle, name='get-vehicle'),
    path('<uuid:vehicle_id>/update/', views.update_vehicle, name='update-vehicle'),
    path('<uuid:vehicle_id>/delete/', views.delete_vehicle, name='delete-vehicle'),
    
    # Driver Assignment
    path('<uuid:vehicle_id>/assign-driver/', views.assign_driver, name='assign-driver'),
    path('<uuid:vehicle_id>/unassign-driver/', views.unassign_driver, name='unassign-driver'),
]