from rest_framework import serializers
from .models import Product, Sale


class ProductSerializer(serializers.ModelSerializer):
    stock_status_label = serializers.ReadOnlyField()
    stock_percentage = serializers.ReadOnlyField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'category', 'price', 'quantity', 'unit',
            'is_subsidy', 'stock_status_label', 'stock_percentage', 'created_at'
        ]


class SaleSerializer(serializers.ModelSerializer):
    product_name = serializers.ReadOnlyField(source='product.name')

    class Meta:
        model = Sale
        fields = ['id', 'product', 'product_name', 'quantity_sold', 'total_price', 'sale_date']
