"""Views for the smart restaurant order forecasting and monitoring app."""

import json
from datetime import timedelta

from django.db.models import Count, Sum
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.safestring import mark_safe

try:
    from sklearn.linear_model import LinearRegression
    import numpy as np
except ImportError:  # pragma: no cover
    LinearRegression = None
    np = None

from .models import Order


def _daily_aggregate(days: int = 30):
    """Return daily aggregates for the past `days` days (inclusive today)."""

    end = timezone.now().date()
    start = end - timedelta(days=days - 1)

    # Build a map of date -> aggregates
    queryset = (
        Order.objects.filter(created_at__date__gte=start, created_at__date__lte=end)
        .extra(select={"date": "date(created_at)"})
        .values("date")
        .annotate(order_count=Count("id"), total_revenue=Sum("total_amount"))
        .order_by("date")
    )

    summaries = {item["date"]: item for item in queryset}

    labels = []
    orders = []
    revenue = []

    for i in range(days):
        date = start + timedelta(days=i)
        labels.append(date.isoformat())
        daily = summaries.get(date)
        orders.append(daily["order_count"] if daily else 0)
        revenue.append(float(daily["total_revenue"] or 0))

    return labels, orders, revenue


def dashboard(request):
    """Render the operations monitoring dashboard."""

    labels, orders, revenue = _daily_aggregate(days=30)

    chart_payload = {
        "labels": labels,
        "orders": orders,
        "revenue": revenue,
    }

    context = {
        "chart_json": mark_safe(json.dumps(chart_payload, ensure_ascii=False)),
    }

    return render(request, "orders/dashboard.html", context)


def forecast(request):
    """Render the order forecast page."""

    days_used = 30
    forecast_days = 7

    labels, orders, _ = _daily_aggregate(days=days_used)

    predicted_labels = []
    predicted_values = []

    if LinearRegression is not None and len(orders) >= 7:
        # Use a simple linear regression to forecast future daily order counts.
        x = np.arange(len(orders)).reshape(-1, 1)
        y = np.array(orders).reshape(-1, 1)
        model = LinearRegression().fit(x, y)
        future_x = np.arange(len(orders), len(orders) + forecast_days).reshape(-1, 1)
        preds = model.predict(future_x).flatten().clip(min=0)
        for i in range(forecast_days):
            date = timezone.now().date() + timedelta(days=i + 1)
            predicted_labels.append(date.isoformat())
            predicted_values.append(int(round(preds[i])))

    history_payload = {
        "labels": labels,
        "orders": orders,
    }
    forecast_payload = {
        "labels": predicted_labels,
        "orders": predicted_values,
    }

    context = {
        "history_json": mark_safe(json.dumps(history_payload, ensure_ascii=False)),
        "forecast_json": mark_safe(json.dumps(forecast_payload, ensure_ascii=False)),
        "has_model": LinearRegression is not None,
    }

    return render(request, "orders/forecast.html", context)


def api_latest(request):
    """An example API endpoint that returns latest totals for JS dashboards."""

    labels, orders, revenue = _daily_aggregate(days=14)

    return JsonResponse({"labels": labels, "orders": orders, "revenue": revenue})
