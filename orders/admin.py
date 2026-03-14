from django.contrib import admin

from .models import Order


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("created_at", "total_amount", "items_count")
    list_filter = ("created_at",)
    ordering = ("-created_at",)
