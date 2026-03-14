from django.db import models


class Order(models.Model):
    """Represents a single order in the smart restaurant."""

    order_id = models.PositiveIntegerField(unique=True, verbose_name="订单ID")
    date = models.DateField(verbose_name="日期")
    item_name = models.CharField(max_length=100, verbose_name="商品名称")
    item_type = models.CharField(max_length=50, verbose_name="商品类型")
    item_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="商品单价")
    quantity = models.PositiveIntegerField(verbose_name="数量")
    transaction_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="交易金额")
    transaction_type = models.CharField(max_length=20, blank=True, verbose_name="交易类型")
    received_by = models.CharField(max_length=10, verbose_name="收银员")
    time_of_sale = models.CharField(max_length=20, verbose_name="销售时间")

    class Meta:
        ordering = ["-date", "-order_id"]
        verbose_name = "订单"
        verbose_name_plural = "订单"

    def __str__(self):
        return f"订单 #{self.order_id} @ {self.date} ({self.item_name})"


class Dish(models.Model):
    """Represents a dish in the restaurant menu."""

    name = models.CharField(max_length=100, unique=True, verbose_name="菜品名称")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="价格")
    category = models.CharField(max_length=50, verbose_name="类别")
    description = models.TextField(blank=True, verbose_name="描述")
    is_available = models.BooleanField(default=True, verbose_name="是否可用")

    class Meta:
        verbose_name = "菜品"
        verbose_name_plural = "菜品"

    def __str__(self):
        return self.name


class OrderItem(models.Model):
    """Represents an item in an order."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='order_items', verbose_name="订单")
    dish = models.ForeignKey(Dish, on_delete=models.CASCADE, verbose_name="菜品")
    quantity = models.PositiveIntegerField(verbose_name="数量")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="单价")  # Price at the time of order

    class Meta:
        verbose_name = "订单明细"
        verbose_name_plural = "订单明细"

    def __str__(self):
        return f"{self.dish.name} x {self.quantity}"
