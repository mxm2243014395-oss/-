from django.contrib import admin

from .models import Order


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_id", "date", "item_name", "quantity", "transaction_amount", "transaction_type", "received_by", "time_of_sale")
    list_filter = ("date", "item_type", "transaction_type", "received_by", "time_of_sale")
    ordering = ("-date", "-order_id")
