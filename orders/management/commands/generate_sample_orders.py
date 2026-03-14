"""Generate synthetic order data for demonstration."""

import random
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from orders.models import Order, Dish, OrderItem


class Command(BaseCommand):
    help = "Generate 1000 synthetic orders with realistic patterns (more orders on weekends, holidays)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=365,
            help="Number of past days to generate orders for (default: 365)",
        )

    def handle(self, *args, **options):
        days = options["days"]

        # First, create some sample dishes if not exist
        dishes = [
            {"name": "宫保鸡丁", "price": 28.00, "category": "主菜"},
            {"name": "麻婆豆腐", "price": 22.00, "category": "主菜"},
            {"name": "鱼香肉丝", "price": 26.00, "category": "主菜"},
            {"name": "糖醋里脊", "price": 30.00, "category": "主菜"},
            {"name": "青椒炒肉", "price": 24.00, "category": "主菜"},
            {"name": "西红柿炒蛋", "price": 18.00, "category": "素菜"},
            {"name": "炒青菜", "price": 15.00, "category": "素菜"},
            {"name": "米饭", "price": 3.00, "category": "主食"},
            {"name": "馒头", "price": 2.00, "category": "主食"},
            {"name": "可乐", "price": 5.00, "category": "饮品"},
            {"name": "雪碧", "price": 5.00, "category": "饮品"},
            {"name": "啤酒", "price": 8.00, "category": "饮品"},
            {"name": "酸梅汤", "price": 6.00, "category": "饮品"},
            {"name": "冰激凌", "price": 12.00, "category": "甜品"},
            {"name": "水果沙拉", "price": 15.00, "category": "甜品"},
        ]

        existing_dishes = Dish.objects.all()
        if not existing_dishes:
            dish_objects = [Dish(**dish) for dish in dishes]
            Dish.objects.bulk_create(dish_objects)
            self.stdout.write("Created sample dishes.")
        else:
            dish_objects = list(existing_dishes)

        # Generate orders
        now = datetime.now()
        start = now - timedelta(days=days)

        orders_to_create = []
        order_items_to_create = []
        order_id_counter = 1

        total_orders = 1000
        orders_per_day_avg = total_orders / days

        for day in range(days):
            day_date = start + timedelta(days=day)
            weekday = day_date.weekday()  # 0=Monday, 6=Sunday

            # Adjust order count: more on weekends, less on weekdays
            if weekday >= 5:  # Saturday, Sunday
                base_orders = int(orders_per_day_avg * 1.5)
            else:
                base_orders = int(orders_per_day_avg * 0.7)

            # Add some randomness
            order_count = max(1, random.randint(base_orders - 2, base_orders + 2))

            for _ in range(order_count):
                if len(orders_to_create) >= total_orders:
                    break

                # Random time between 10:00 and 22:00
                hour = random.randint(10, 21)
                minute = random.randint(0, 59)
                time_of_sale = f"{hour:02d}:{minute:02d}"

                # Select random dishes for this order (1-5 items)
                num_items = random.randint(1, 5)
                selected_dishes = random.sample(dish_objects, num_items)

                total_amount = 0
                total_quantity = 0
                first_item_name = selected_dishes[0].name
                first_item_type = selected_dishes[0].category
                first_item_price = selected_dishes[0].price

                # Create Order
                order = Order(
                    order_id=order_id_counter,
                    date=day_date.date(),
                    item_name=first_item_name,  # Use first item for legacy field
                    item_type=first_item_type,
                    item_price=first_item_price,
                    quantity=1,  # Will update later
                    transaction_amount=0,  # Will update
                    transaction_type="现金",  # Or random
                    received_by=f"收银员{random.randint(1,5)}",
                    time_of_sale=time_of_sale,
                )
                orders_to_create.append(order)

                # Create OrderItems
                for dish in selected_dishes:
                    quantity = random.randint(1, 3)
                    price = dish.price
                    order_item = OrderItem(
                        order=order,
                        dish=dish,
                        quantity=quantity,
                        price=price,
                    )
                    order_items_to_create.append(order_item)
                    total_amount += price * quantity
                    total_quantity += quantity

                # Update order totals
                order.quantity = total_quantity
                order.transaction_amount = total_amount

                order_id_counter += 1

            if len(orders_to_create) >= total_orders:
                break

        # Bulk create
        Order.objects.bulk_create(orders_to_create[:total_orders])
        OrderItem.objects.bulk_create(order_items_to_create)

        self.stdout.write(self.style.SUCCESS(f"Generated {len(orders_to_create)} sample orders with order items."))
