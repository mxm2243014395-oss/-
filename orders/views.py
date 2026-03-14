"""Views for the smart restaurant order forecasting and monitoring app."""

import json
import logging
from datetime import timedelta, datetime
from functools import lru_cache
from typing import List, Tuple, Optional, Dict, Any

from django.core.cache import cache
from django.db.models import Count, Sum, Avg
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

try:
    from sklearn.linear_model import LinearRegression
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    from sklearn.svm import SVR
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_absolute_percentage_error
    import numpy as np
except ImportError:  # pragma: no cover
    LinearRegression = None
    RandomForestRegressor = None
    GradientBoostingRegressor = None
    SVR = None
    StandardScaler = None
    train_test_split = None
    mean_absolute_percentage_error = None
    np = None

from .models import Order

logger = logging.getLogger(__name__)


@lru_cache(maxsize=32)
def _get_daily_aggregates_cached(days: int) -> List[dict]:
    """Cached version of daily aggregates query with optimized performance."""
    end = timezone.now().date()
    start = end - timedelta(days=days - 1)

    # Use iterator for memory efficiency with large datasets
    queryset = (
        Order.objects.filter(date__gte=start, date__lte=end)
        .values("date")
        .annotate(
            order_count=Count("id"),
            total_revenue=Sum("transaction_amount"),
            avg_order_value=Avg("transaction_amount"),
            total_items=Sum("quantity")
        )
        .order_by("date")
    )

    # For large datasets, limit memory usage
    if days > 365:  # If more than a year of data
        return list(queryset.iterator())
    else:
        return list(queryset)


def _get_daily_aggregates_from_orders(orders: List[Order]) -> List[dict]:
    """Aggregate daily data from a list of orders, optimized for large datasets."""
    if not orders:
        return []

    # Group orders by date
    daily_groups = {}
    for order in orders:
        date_str = order.date.isoformat()
        if date_str not in daily_groups:
            daily_groups[date_str] = {
                'date': order.date,
                'total_orders': 0,
                'total_revenue': 0.0,
                'total_items': 0
            }
        daily_groups[date_str]['total_orders'] += 1
        daily_groups[date_str]['total_revenue'] += float(order.transaction_amount or 0)
        daily_groups[date_str]['total_items'] += order.quantity or 0

    # Convert to list and sort by date
    result = list(daily_groups.values())
    result.sort(key=lambda x: x['date'])

    return result


def _daily_aggregate(days: int = 30, sample_data: bool = False) -> Tuple[List[str], List[int], List[float]]:
    """Return daily aggregates for the past `days` days (inclusive today).

    Args:
        days: Number of days to aggregate
        sample_data: Whether to sample data for large datasets

    Returns:
        Tuple of (labels, orders, revenue)
    """
    cache_key = f"daily_aggregates_{days}_{sample_data}"
    cached_data = cache.get(cache_key)

    if cached_data:
        return cached_data

    queryset = _get_daily_aggregates_cached(days)
    summaries = {item["date"]: item for item in queryset}

    end = timezone.now().date()
    start = end - timedelta(days=days - 1)

    labels = []
    orders = []
    revenue = []

    # For large datasets, sample every N days to reduce data points
    if sample_data and days > 90:
        sample_interval = max(1, days // 90)  # Sample to ~90 points max
        for i in range(0, days, sample_interval):
            date = start + timedelta(days=i)
            labels.append(date.isoformat())
            daily = summaries.get(date)
            orders.append(daily["order_count"] if daily else 0)
            revenue.append(float(daily["total_revenue"] if daily else 0))
    else:
        for i in range(days):
            date = start + timedelta(days=i)
            labels.append(date.isoformat())
            daily = summaries.get(date)
            orders.append(daily["order_count"] if daily else 0)
            revenue.append(float(daily["total_revenue"] if daily else 0))

    result = (labels, orders, revenue)
    # Cache for 10 minutes for large datasets, 5 minutes for small
    cache_timeout = 600 if days > 365 else 300
    cache.set(cache_key, result, cache_timeout)
    return result


def _forecast_orders_simple(orders: List[int], days_used: int, forecast_days: int) -> Tuple[List[str], List[int]]:
    """
    简易订单预测函数，使用线性回归模型预测未来订单数量。

    该函数通过加入“星期几”作为第二特征，让模型学习到周末客流激增的周期性规律，
    从而提高预测准确性。适用于毕业设计答辩的核心演示。

    Args:
        orders: 历史订单数量列表（每日订单数）
        days_used: 使用的历史天数
        forecast_days: 需要预测的天数

    Returns:
        Tuple of (predicted_labels, predicted_values) - 预测日期标签和预测订单数量

    注意：
        - 如果历史数据不足7天，将返回空列表（避免预测不准确）
        - 使用两个特征：天数递增索引和星期几（0-6，0=周一，6=周日）
        - 模型会自动学习周末订单量更高的规律
    """
    # 数据健壮性检查：历史数据不足7天时不进行预测
    if not orders or len(orders) < 7:
        logger.warning("历史数据不足7天，无法进行可靠的订单预测")
        return [], []

    predicted_labels = []
    predicted_values = []

    # 对于大数据集，进行采样以提高性能（限制为60天）
    if len(orders) > 60:
        sample_size = 60
        # 使用线性插值采样，保持数据分布
        indices = np.linspace(0, len(orders) - 1, sample_size, dtype=int)
        orders_sampled = [orders[i] for i in indices]
        days_used_sampled = sample_size
    else:
        orders_sampled = orders
        days_used_sampled = days_used

    # 构建训练特征矩阵
    # 特征1：天数递增索引（0, 1, 2, ...）- 捕捉时间趋势
    # 特征2：星期几（0-6）- 捕捉周期性规律（如周末高峰）
    x_train = []
    # 计算历史数据的起始日期
    base_date = timezone.now().date() - timedelta(days=days_used_sampled - 1)

    for i in range(len(orders_sampled)):
        date_val = base_date + timedelta(days=i)
        features = [
            i,  # 天数递增索引 - 反映时间序列的趋势
            date_val.weekday(),  # 星期几 (0=周一, 6=周日) - 捕捉周末效应
        ]
        x_train.append(features)

    # 转换为numpy数组
    x = np.array(x_train)
    y = np.array(orders_sampled)

    # 初始化模型变量
    model = None

    # 尝试使用线性回归模型
    if LinearRegression is not None:
        try:
            model = LinearRegression()
            # 训练模型：学习历史数据中的趋势和周期性规律
            model.fit(x, y)
            logger.info("线性回归模型训练成功，特征包括天数索引和星期几")
        except Exception as e:
            logger.error(f"线性回归模型训练失败: {e}")
            model = None

    # 如果模型训练成功，进行预测
    if model is not None:
        # 生成未来预测的特征
        future_x = []
        current_date = timezone.now().date()

        for i in range(forecast_days):
            future_date = current_date + timedelta(days=i + 1)
            features = [
                len(orders_sampled) + i,  # 未来天数索引（延续历史序列）
                future_date.weekday(),    # 未来日期的星期几
            ]
            future_x.append(features)

        future_x = np.array(future_x)
        # 使用训练好的模型进行预测
        preds = model.predict(future_x)

        # 应用合理的约束条件，避免预测值过高或为负
        max_historical = max(orders) if orders else 0
        # 限制预测值在0到历史最大值的1.5倍之间
        preds = np.clip(preds, 0, max_historical * 1.5)

        # 生成预测结果
        for i in range(forecast_days):
            date = current_date + timedelta(days=i + 1)
            predicted_labels.append(date.isoformat())
            # 取整预测值，确保为整数
            predicted_values.append(int(round(preds[i])))

        logger.info(f"成功预测未来{forecast_days}天的订单数量")

    # 如果模型不可用，返回空结果
    return predicted_labels, predicted_values


def _forecast_orders(orders: List[int], days_used: int, forecast_days: int, model_type: str = 'auto') -> Tuple[List[str], List[int], Dict[str, Any]]:
    """Advanced order forecasting with multiple models, confidence intervals, and enhanced features.

    Args:
        orders: Historical order counts
        days_used: Number of historical days
        forecast_days: Number of days to forecast
        model_type: Type of model to use ('auto', 'linear', 'rf', 'gb', 'svr')

    Returns:
        Tuple of (predicted_labels, predicted_values, metadata)
    """
    if not orders or len(orders) < 7:
        return [], [], {}

    predicted_labels = []
    predicted_values = []
    metadata = {
        'model_used': 'none',
        'confidence_intervals': [],
        'accuracy_score': None,
        'feature_importance': {},
        'seasonal_patterns': {},
    }

    # For large datasets, sample data to reduce computation time
    if len(orders) > 365:  # More than a year of data
        sample_size = min(365, len(orders))  # Sample to 1 year max
        indices = np.linspace(0, len(orders) - 1, sample_size, dtype=int)
        orders_sampled = [orders[i] for i in indices]
        days_used_sampled = len(orders_sampled)
    else:
        orders_sampled = orders
        days_used_sampled = days_used

    # Enhanced feature engineering
    x_train = []
    base_date = timezone.now().date() - timedelta(days=days_used_sampled - 1)

    for i in range(len(orders_sampled)):
        date_val = base_date + timedelta(days=i)
        features = [
            i,  # Day index
            date_val.weekday(),  # Day of week (0-6)
            date_val.month,  # Month
            1 if date_val.weekday() >= 5 else 0,  # Weekend flag
            date_val.day,  # Day of month
            (date_val - base_date).days,  # Days since start
            np.sin(2 * np.pi * i / 7),  # Weekly seasonality
            np.cos(2 * np.pi * i / 7),
            np.sin(2 * np.pi * i / 30),  # Monthly seasonality
            np.cos(2 * np.pi * i / 30),
        ]
        x_train.append(features)

    x = np.array(x_train)
    y = np.array(orders_sampled)

    # Feature scaling
    scaler = StandardScaler() if StandardScaler else None
    if scaler:
        x_scaled = scaler.fit_transform(x)
    else:
        x_scaled = x

    # Model selection and training
    model = None
    best_score = float('inf')

    models_to_try = []

    if model_type == 'auto':
        # Try multiple models and pick the best
        if LinearRegression:
            models_to_try.append(('linear', LinearRegression()))
        if RandomForestRegressor and len(orders_sampled) > 50:
            models_to_try.append(('rf', RandomForestRegressor(
                n_estimators=min(50, len(orders_sampled) // 10),
                max_depth=10,
                random_state=42,
                n_jobs=-1
            )))
        if GradientBoostingRegressor and len(orders_sampled) > 30:
            models_to_try.append(('gb', GradientBoostingRegressor(
                n_estimators=50,
                max_depth=5,
                random_state=42
            )))
        if SVR and len(orders_sampled) > 20:
            models_to_try.append(('svr', SVR(kernel='rbf', C=1.0, epsilon=0.1)))
    else:
        # Use specific model
        if model_type == 'linear' and LinearRegression:
            models_to_try.append(('linear', LinearRegression()))
        elif model_type == 'rf' and RandomForestRegressor:
            models_to_try.append(('rf', RandomForestRegressor(
                n_estimators=min(50, len(orders_sampled) // 10),
                max_depth=10,
                random_state=42,
                n_jobs=-1
            )))
        elif model_type == 'gb' and GradientBoostingRegressor:
            models_to_try.append(('gb', GradientBoostingRegressor(
                n_estimators=50,
                max_depth=5,
                random_state=42
            )))
        elif model_type == 'svr' and SVR:
            models_to_try.append(('svr', SVR(kernel='rbf', C=1.0, epsilon=0.1)))

    # Train and evaluate models
    for model_name, candidate_model in models_to_try:
        try:
            if len(orders_sampled) >= 14:  # Cross-validation for accuracy
                train_x, test_x, train_y, test_y = train_test_split(
                    x_scaled, y, test_size=0.2, random_state=42
                )
                candidate_model.fit(train_x, train_y)
                pred_y = candidate_model.predict(test_x)
                score = mean_absolute_percentage_error(test_y, pred_y) if mean_absolute_percentage_error else abs(pred_y - test_y).mean()
            else:
                candidate_model.fit(x_scaled, y)
                score = 0  # No validation possible

            if score < best_score:
                best_score = score
                model = candidate_model
                metadata['model_used'] = model_name
                metadata['accuracy_score'] = round(score * 100, 2) if score > 0 else None

        except Exception as e:
            logger.warning(f"Model {model_name} failed: {e}")
            continue

    if model is not None:
        # Generate future features
        future_x = []
        current_date = timezone.now().date()

        for i in range(forecast_days):
            date_val = current_date + timedelta(days=i + 1)
            features = [
                len(orders_sampled) + i,  # Day index
                date_val.weekday(),  # Day of week
                date_val.month,  # Month
                1 if date_val.weekday() >= 5 else 0,  # Weekend flag
                date_val.day,  # Day of month
                (date_val - base_date).days,  # Days since start
                np.sin(2 * np.pi * (len(orders_sampled) + i) / 7),  # Weekly seasonality
                np.cos(2 * np.pi * (len(orders_sampled) + i) / 7),
                np.sin(2 * np.pi * (len(orders_sampled) + i) / 30),  # Monthly seasonality
                np.cos(2 * np.pi * (len(orders_sampled) + i) / 30),
            ]
            future_x.append(features)

        future_x = np.array(future_x)
        if scaler:
            future_x_scaled = scaler.transform(future_x)
        else:
            future_x_scaled = future_x

        preds = model.predict(future_x_scaled)

        # Calculate confidence intervals using prediction variance
        if hasattr(model, 'predict') and len(orders_sampled) > 20:
            # Simple bootstrap for confidence intervals
            n_boot = 100
            boot_preds = []
            for _ in range(n_boot):
                indices = np.random.choice(len(x_scaled), len(x_scaled), replace=True)
                boot_x = x_scaled[indices]
                boot_y = y[indices]
                try:
                    model.fit(boot_x, boot_y)
                    boot_pred = model.predict(future_x_scaled)
                    boot_preds.append(boot_pred)
                except:
                    continue

            if boot_preds:
                boot_preds = np.array(boot_preds)
                ci_lower = np.percentile(boot_preds, 5, axis=0)
                ci_upper = np.percentile(boot_preds, 95, axis=0)
                metadata['confidence_intervals'] = [
                    {'lower': int(max(0, ci_lower[i])), 'upper': int(ci_upper[i])}
                    for i in range(len(preds))
                ]

        # Apply constraints and smoothing
        max_historical = max(orders) if orders else 0
        preds = np.clip(preds, 0, max_historical * 1.5)  # Reasonable upper bound

        # Extract feature importance if available
        if hasattr(model, 'feature_importances_'):
            feature_names = ['day_index', 'weekday', 'month', 'weekend', 'day', 'days_since_start',
                           'weekly_sin', 'weekly_cos', 'monthly_sin', 'monthly_cos']
            metadata['feature_importance'] = {
                feature_names[i]: round(imp * 100, 2)
                for i, imp in enumerate(model.feature_importances_)
            }

        # Analyze seasonal patterns
        weekday_avg = {}
        for i, order_count in enumerate(orders_sampled):
            date_val = base_date + timedelta(days=i)
            wd = date_val.weekday()
            if wd not in weekday_avg:
                weekday_avg[wd] = []
            weekday_avg[wd].append(order_count)

        metadata['seasonal_patterns'] = {
            'weekday_avg': {k: round(np.mean(v), 1) for k, v in weekday_avg.items()},
            'weekend_boost': round(np.mean([
                np.mean(weekday_avg.get(5, [0])) + np.mean(weekday_avg.get(6, [0]))
            ]) / max(np.mean([np.mean(weekday_avg.get(i, [0])) for i in range(5)]), 1) - 1, 2)
        }

        for i in range(forecast_days):
            date = current_date + timedelta(days=i + 1)
            predicted_labels.append(date.isoformat())
            predicted_values.append(int(round(preds[i])))

    return predicted_labels, predicted_values, metadata


def dashboard(request):
    """Dashboard view with optimized data handling for large datasets."""
    # Get filter parameters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    restaurant = request.GET.get('restaurant')
    limit = request.GET.get('limit', '1000')  # Default limit for large datasets

    try:
        limit = int(limit)
        if limit <= 0:
            limit = 1000
        elif limit > 10000:  # Cap at 10k for performance
            limit = 10000
    except ValueError:
        limit = 1000

    # Build query with efficient filtering
    orders_query = Order.objects.all()

    if start_date:
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            orders_query = orders_query.filter(date__gte=start_date_obj)
        except ValueError:
            pass

    if end_date:
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            orders_query = orders_query.filter(date__lte=end_date_obj)
        except ValueError:
            pass

    if restaurant:
        orders_query = orders_query.filter(restaurant_name__icontains=restaurant)

    # Apply limit for performance
    orders_query = orders_query.order_by('-date')[:limit]

    # Use iterator for memory efficiency with large datasets
    orders = list(orders_query)

    # Get aggregated data with caching
    daily_data = _get_daily_aggregates_from_orders(orders)

    # Prepare chart data
    chart_labels = [item['date'].isoformat() for item in daily_data]
    chart_values = [item['total_orders'] for item in daily_data]

    # Calculate summary statistics
    total_orders = sum(item['total_orders'] for item in daily_data)
    total_revenue = sum(item['total_revenue'] for item in daily_data)
    avg_order_value = total_revenue / total_orders if total_orders > 0 else 0

    # Get top items (limit to top 10 for performance)
    item_counts = {}
    for order in orders:
        if order.item_name:
            item_counts[order.item_name] = item_counts.get(order.item_name, 0) + order.quantity

    top_items = sorted(item_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    # Get top dishes from OrderItem (new feature for graduation project)
    from django.db.models import Sum
    top_dishes_query = OrderItem.objects.filter(
        order__in=orders_query
    ).values('dish__name').annotate(
        total_quantity=Sum('quantity')
    ).order_by('-total_quantity')[:5]

    top_dishes = list(top_dishes_query)
    top_dishes_labels = [item['dish__name'] for item in top_dishes]
    top_dishes_values = [item['total_quantity'] for item in top_dishes]

    context = {
        'total_orders': total_orders,
        'total_revenue': f"{total_revenue:.2f}",
        'avg_order_value': f"{avg_order_value:.2f}",
        'chart_labels': json.dumps(chart_labels),
        'chart_values': json.dumps(chart_values),
        'top_items': top_items,
        'top_dishes_labels': json.dumps(top_dishes_labels),
        'top_dishes_values': json.dumps(top_dishes_values),
        'start_date': start_date,
        'end_date': end_date,
        'restaurant': restaurant,
        'limit': limit,
        'orders_count': len(orders),
    }

    return render(request, 'orders/dashboard.html', context)


def forecast(request):
    """Render the order forecast page with simple and effective analytics."""

    # Get simple parameters from request
    days_used = int(request.GET.get('days', 30))
    forecast_days = int(request.GET.get('forecast', 7))

    # Validate parameters (keep it simple)
    days_used = max(7, min(days_used, 90))  # Between 7 and 90 days
    forecast_days = max(1, min(forecast_days, 14))  # Between 1 and 14 days

    # Get historical data
    labels, orders, _ = _daily_aggregate(days=days_used)

    # Simple forecasting with basic model selection
    predicted_labels, predicted_values = _forecast_orders_simple(orders, days_used, forecast_days)

    # Calculate basic accuracy if we have enough data
    accuracy_info = {}
    if len(orders) >= 14:
        train_orders = orders[:-7]
        test_orders = orders[-7:]

        if train_orders:
            _, test_preds = _forecast_orders_simple(train_orders, len(train_orders), 7)
            if test_preds and len(test_preds) == len(test_orders):
                # Simple MAPE calculation
                mape = np.mean([
                    abs(actual - pred) / max(actual, 1) * 100
                    for actual, pred in zip(test_orders, test_preds)
                ])
                accuracy_info['mape'] = round(mape, 1)

    # Prepare data for templates
    history_payload = {
        "labels": labels,
        "orders": orders,
    }
    forecast_payload = {
        "labels": predicted_labels,
        "orders": predicted_values,
    }

    context = {
        "history_data": history_payload,
        "forecast_data": forecast_payload,
        "has_model": LinearRegression is not None,
        "accuracy_info": accuracy_info,
        "forecast_days": forecast_days,
        "historical_days": days_used,
        "total_historical": sum(orders),
        "avg_historical": round(sum(orders) / len(orders), 1) if orders else 0,
        "total_forecast": sum(predicted_values),
        "avg_forecast": round(sum(predicted_values) / len(predicted_values), 1) if predicted_values else 0,
    }

    return render(request, "orders/forecast.html", context)


def api_latest(request):
    """An example API endpoint that returns latest totals for JS dashboards."""

    labels, orders, revenue = _daily_aggregate(days=14)

    return JsonResponse({"labels": labels, "orders": orders, "revenue": revenue})