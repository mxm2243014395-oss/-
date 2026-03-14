# 智慧餐厅订单预测与运营监控可视化

这是一个基于 Django 的简易智慧餐厅订单预测与运营监控可视化系统示例。

## 功能亮点

- ✅ **运营监控仪表盘**：展示最近 30 天订单数量与营收趋势
- ✅ **订单预测模块**：基于历史订单进行未来 7 天订单需求预测（采用线性回归模型）
- ✅ **样例数据生成**：一键生成假数据用于演示和本地测试

## 运行方式

```bash
# 1. 创建并激活 Python 虚拟环境（推荐）
python -m venv .venv
source .venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行数据库迁移
python manage.py migrate

# 4. 生成示例订单数据（可选）
python manage.py generate_sample_orders --days 60

# 5. 启动开发服务器
python manage.py runserver
```

然后访问：
- 运营监控： http://127.0.0.1:8000/
- 订单预测： http://127.0.0.1:8000/forecast/

## 说明

- 若要启用预测功能，请确保已安装 `scikit-learn`（已在 `requirements.txt` 中）。
- 可在 Django Admin 中查看订单数据：
  - 创建超级用户：`python manage.py createsuperuser`
  - 登录地址： http://127.0.0.1:8000/admin/
