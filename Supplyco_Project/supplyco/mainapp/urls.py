from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.user_register, name='user_register'),
    path('login/', views.user_login, name='user_login'),
    path('logout/', views.user_logout, name='user_logout'),
    path('products/', views.user_products, name='user_products'),
    path('admin_dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('add_product/', views.add_product, name='add_product'),
    path('edit_product/<int:pk>/', views.edit_product, name='edit_product'),
    path('delete_product/<int:pk>/', views.delete_product, name='delete_product'),
    path('sell_product/<int:pk>/', views.sell_product, name='sell_product'),
    path('stock_analytics/', views.stock_analytics, name='stock_analytics'),
    path('staff_dashboard/', views.staff_dashboard, name='staff_dashboard'),
    path('warehouse_management/', views.warehouse_management, name='warehouse_management'),
    path('stock_arrivals/', views.stock_arrivals, name='stock_arrivals'),
    path('mark_bill_given/<int:customer_id>/', views.mark_bill_given, name='mark_bill_given'),
    path('customer_detail/<int:customer_id>/', views.customer_purchase_detail, name='customer_purchase_detail'),
    path('api/stock/', views.api_stock_levels, name='api_stock_levels'),

    # Flutter / REST API endpoints
    path('api/flutter/login/', views.flutter_login, name='flutter_login'),
    path('api/flutter/logout/', views.flutter_logout, name='flutter_logout'),
    path('api/flutter/products/', views.flutter_products, name='flutter_products'),
    path('api/flutter/dashboard/', views.flutter_dashboard, name='flutter_dashboard'),
    path('api/flutter/analytics/', views.flutter_analytics, name='flutter_analytics'),
    path('api/flutter/products/add/', views.flutter_add_product, name='flutter_add_product'),
    path('api/flutter/products/<int:pk>/edit/', views.flutter_edit_product, name='flutter_edit_product'),
    path('api/flutter/products/<int:pk>/delete/', views.flutter_delete_product, name='flutter_delete_product'),
    path('api/flutter/products/<int:pk>/sell/', views.flutter_sell_product, name='flutter_sell_product'),
]
