"""Generate synthetic order data for demonstration."""

import random
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand

from orders.models import Order


class Command(BaseCommand):
    help = "Generate synthetic orders for the past N days."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=60,
            help="Number of past days to generate orders for (default: 60)",
        )
        parser.add_argument(
            "--min-orders",
            type=int,
            default=5,
            help="Minimum number of orders per day (default: 5)",
        )
        parser.add_argument(
            "--max-orders",
            type=int,
            default=30,
            help="Maximum number of orders per day (default: 30)",
        )

    def handle(self, *args, **options):
        days = options["days"]
        min_orders = options["min_orders"]
        max_orders = options["max_orders"]

        now = datetime.utcnow()
        start = now - timedelta(days=days)

        self.stdout.write("Generating sample order data...")

        for day in range(days):
            day_date = start + timedelta(days=day)
            order_count = random.randint(min_orders, max_orders)

            for _ in range(order_count):
                created_at = day_date + timedelta(
                    hours=random.randint(9, 21),
                    minutes=random.randint(0, 59),
                    seconds=random.randint(0, 59),
                )
                amount = round(random.uniform(20.0, 200.0), 2)
                items_count = random.randint(1, 6)

                Order.objects.create(
                    created_at=created_at,
                    total_amount=amount,
                    items_count=items_count,
                )

        self.stdout.write(self.style.SUCCESS("Sample orders generated."))
