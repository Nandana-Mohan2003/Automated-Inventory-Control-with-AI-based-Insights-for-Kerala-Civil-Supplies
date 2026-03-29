from django.contrib import admin
from .models import Product, Warehouse, WarehouseStock, StockArrival, StockArrivalItem, StockTransferLog

for i in [Product, Warehouse, WarehouseStock, StockArrival, StockArrivalItem, StockTransferLog]:
    admin.site.register(i)
