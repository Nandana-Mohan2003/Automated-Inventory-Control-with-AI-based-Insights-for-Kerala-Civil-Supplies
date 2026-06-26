from django.db.models.signals import post_save
from django.dispatch import receiver
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import Product, Sale

@receiver(post_save, sender=Product)
def product_updated(sender, instance, **kwargs):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "stock_updates",
        {
            "type": "stock_update",
            "message": {
                "id": instance.id,
                "name": instance.name,
                "quantity": instance.quantity,
                "unit": instance.unit,
                "percentage": instance.stock_percentage,
                "status_class": instance.stock_status_class,
                "status_label": instance.stock_status_label,
                "is_subsidy": instance.is_subsidy,
                "price": float(instance.price),
            }
        }
    )

@receiver(post_save, sender=Sale)
def sale_recorded(sender, instance, **kwargs):
    # When a sale is recorded, the product quantity usually changes.
    product = instance.product
    product_updated(Product, product)
