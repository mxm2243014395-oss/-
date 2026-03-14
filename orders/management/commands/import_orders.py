"""Import order data from CSV text."""

import csv
import random
from io import StringIO
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from orders.models import Order


class Command(BaseCommand):
    help = "Import order data from CSV text"

    def handle(self, *args, **options):
        csv_data = """order_id,date,item_name,item_type,item_price,quantity,transaction_amount,transaction_type,received_by,time_of_sale
1,07-03-2022,Aalopuri,Fastfood,20,13,260,,Mr.,Night
2,8/23/2022,Vadapav,Fastfood,20,15,300,Cash,Mr.,Afternoon
3,11/20/2022,Vadapav,Fastfood,20,1,20,Cash,Mr.,Afternoon
4,02-03-2023,Sugarcane juice,Beverages,25,6,150,Online,Mr.,Night
5,10-02-2022,Sugarcane juice,Beverages,25,8,200,Online,Mr.,Evening
6,11/14/2022,Vadapav,Fastfood,20,10,200,Cash,Mr.,Evening
7,05-03-2022,Sugarcane juice,Beverages,25,9,225,Cash,Mr.,Evening
8,12/22/2022,Panipuri,Fastfood,20,14,280,Online,Mr.,Night
9,06-10-2022,Panipuri,Fastfood,20,1,20,Cash,Mrs.,Morning
10,9/16/2022,Panipuri,Fastfood,20,5,100,Online,Mr.,Afternoon
11,12-01-2022,Frankie,Fastfood,50,8,400,Online,Mrs.,Afternoon
12,07-12-2022,Vadapav,Fastfood,20,8,160,Online,Mrs.,Night
13,12/22/2022,Panipuri,Fastfood,20,9,180,Online,Mrs.,Afternoon
14,11/25/2022,Frankie,Fastfood,50,4,200,Online,Mr.,Morning
15,02-03-2023,Aalopuri,Fastfood,20,3,60,Cash,Mrs.,Evening
16,4/14/2022,Sandwich,Fastfood,60,11,660,,Mrs.,Midnight
17,10/16/2022,Panipuri,Fastfood,20,11,220,Cash,Mrs.,Morning
18,11-05-2022,Panipuri,Fastfood,20,10,200,Cash,Mrs.,Night
19,8/22/2022,Panipuri,Fastfood,20,11,220,Cash,Mrs.,Night
20,9/15/2022,Cold coffee,Beverages,40,10,400,Online,Mr.,Night"""

        reader = csv.DictReader(StringIO(csv_data))
        for row in reader:
            date_str = row['date']
            # Parse date, handle different formats
            try:
                date = datetime.strptime(date_str, '%m-%d-%Y').date()
            except ValueError:
                try:
                    date = datetime.strptime(date_str, '%m/%d/%Y').date()
                except ValueError:
                    self.stdout.write(self.style.ERROR(f"Invalid date format: {date_str}"))
                    continue

            # Shift date to recent period
            base_date = datetime(2026, 1, 1).date()
            days_offset = (date - datetime(2022, 1, 1).date()).days
            new_date = base_date + timedelta(days=days_offset)
            if new_date > timezone.now().date():
                new_date = timezone.now().date() - timedelta(days=random.randint(0, 30))

            Order.objects.create(
                order_id=int(row['order_id']),
                date=new_date,
                item_name=row['item_name'],
                item_type=row['item_type'],
                item_price=float(row['item_price']),
                quantity=int(row['quantity']),
                transaction_amount=float(row['transaction_amount']),
                transaction_type=row['transaction_type'],
                received_by=row['received_by'],
                time_of_sale=row['time_of_sale'],
            )

        self.stdout.write(self.style.SUCCESS("Successfully imported order data"))