from django.db import models


class Order(models.Model):
    """Represents a single order in the smart restaurant."""

    created_at = models.DateTimeField()
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    items_count = models.PositiveIntegerField()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.pk} @ {self.created_at:%Y-%m-%d %H:%M} (￥{self.total_amount})"
