import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)

BASE = Path(__file__).resolve().parents[1]
OUTPUT = BASE / "sql" / "seed_ecommerce_large.sql"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

regions = ["North", "South", "East", "West", "Central"]
customer_names = [
    ("Ava", "Patel"), ("Leo", "Martin"), ("Nia", "Johnson"), ("Omar", "Ali"), ("Sofia", "Nguyen"),
    ("Ethan", "Brown"), ("Mila", "Davis"), ("Ryan", "Wilson"), ("Zoe", "Taylor"), ("Kai", "Thomas"),
    ("Priya", "Sharma"), ("Noah", "Lee"), ("Emma", "Clark"), ("Liam", "Harris"), ("Isla", "Walker"),
    ("Lucas", "Moore"), ("Harper", "Hall"), ("Mason", "Young"), ("Ella", "Allen"), ("James", "King")
]
products = [
    (101, "SKU-123", "Wireless Headphones", "Electronics", 129.99),
    (102, "SKU-456", "Running Shoes", "Footwear", 89.50),
    (103, "SKU-789", "Backpack", "Accessories", 54.00),
    (104, "SKU-246", "Coffee Grinder", "Home", 75.00),
    (105, "SKU-357", "Fitness Tracker", "Electronics", 149.95),
    (106, "SKU-468", "Office Chair", "Furniture", 210.00),
    (107, "SKU-579", "Desk Lamp", "Home", 42.50),
    (108, "SKU-680", "Hiking Backpack", "Outdoors", 99.99),
    (109, "SKU-791", "Yoga Mat", "Fitness", 34.95),
    (110, "SKU-802", "Bluetooth Speaker", "Electronics", 64.99),
]

customer_count = 1000
order_count = 5000

# Generate customer inserts
customer_lines = [
    "INSERT INTO ecommerce.customers (customer_id, first_name, last_name, email, signup_date, region, customer_tier) VALUES"
]
for i in range(1, customer_count + 1):
    first, last = customer_names[(i - 1) % len(customer_names)]
    region = regions[(i - 1) % len(regions)]
    tier = ["Gold", "Silver", "Platinum", "Bronze"][i % 4]
    signup = (datetime(2023, 1, 1) + timedelta(days=i * 7)).strftime("%Y-%m-%d %H:%M:%S")
    email = f"{first.lower()}.{last.lower()}{i}@example.com"
    customer_lines.append(
        f"({i}, '{first}', '{last}', '{email}', '{signup}', '{region}', '{tier}')")
    if i % 100 == 0 or i == customer_count:
        customer_lines[-1] += ";"
        if i != customer_count:
            customer_lines.append("INSERT INTO ecommerce.customers (customer_id, first_name, last_name, email, signup_date, region, customer_tier) VALUES")

customer_sql = "\n".join(customer_lines)

# Generate product inserts
product_lines = [
    "INSERT INTO ecommerce.products (product_id, sku, product_name, category, price) VALUES"
]
for idx, product in enumerate(products, start=1):
    product_lines.append(f"({product[0]}, '{product[1]}', '{product[2]}', '{product[3]}', {product[4]})")
product_lines[-1] += ";"
product_sql = "\n".join(product_lines)

# Generate orders and order items
order_lines = [
    "INSERT INTO ecommerce.orders (order_id, customer_id, order_date, total_amount, status, payment_status, shipping_status, region) VALUES"
]
item_lines = [
    "INSERT INTO ecommerce.order_items (order_item_id, order_id, product_id, sku, quantity, unit_price) VALUES"
]
order_item_counter = 1
for order_id in range(1, order_count + 1):
    customer_id = random.randint(1, customer_count)
    region = regions[random.randint(0, len(regions) - 1)]
    order_day = datetime(2026, 1, 1) + timedelta(days=random.randint(0, 300))
    order_hour = random.randint(0, 23)
    order_minute = random.randint(0, 59)
    order_date = order_day.replace(hour=order_hour, minute=order_minute)

    line_count = random.randint(1, 3)
    subtotal = 0.0
    chosen_products = random.sample(products, line_count)
    for product in chosen_products:
        qty = random.randint(1, 4)
        price = float(product[4])
        subtotal += price * qty
    status_choices = ["processing", "shipped", "delivered", "returned", "cancelled"]
    status = random.choices(status_choices, weights=[20, 35, 30, 10, 5], k=1)[0]
    payment_status = "paid" if status in {"processing", "shipped", "delivered", "returned"} else "pending"
    shipping_status = "pending" if status == "processing" else "in_transit" if status == "shipped" else "delivered" if status == "delivered" else "returned" if status == "returned" else "cancelled"
    order_lines.append(f"({order_id}, {customer_id}, '{order_date.strftime('%Y-%m-%d %H:%M:%S')}', {round(subtotal, 2)}, '{status}', '{payment_status}', '{shipping_status}', '{region}')")

    for product in chosen_products:
        qty = random.randint(1, 3)
        item_price = float(product[4])
        item_lines.append(f"({order_item_counter}, {order_id}, {product[0]}, '{product[1]}', {qty}, {round(item_price, 2)})")
        order_item_counter += 1

    if order_id % 200 == 0 or order_id == order_count:
        order_lines[-1] += ";"
        item_lines[-1] += ";"
        if order_id != order_count:
            order_lines.append("INSERT INTO ecommerce.orders (order_id, customer_id, order_date, total_amount, status, payment_status, shipping_status, region) VALUES")
            item_lines.append("INSERT INTO ecommerce.order_items (order_item_id, order_id, product_id, sku, quantity, unit_price) VALUES")

order_sql = "\n".join(order_lines)
items_sql = "\n".join(item_lines)

# Inventory
inventory_lines = [
    "INSERT INTO ecommerce.inventory (inventory_id, product_id, sku, stock_qty, reorder_level, warehouse, updated_at) VALUES"
]
for idx, product in enumerate(products, start=1):
    inventory_lines.append(f"({idx}, {product[0]}, '{product[1]}', {random.randint(5, 120)}, {random.randint(5, 20)}, 'WH-{idx % 5 + 1}', '{(datetime(2026, 1, 1) + timedelta(days=idx)).strftime('%Y-%m-%d %H:%M:%S')}')")
inventory_lines[-1] += ";"
inventory_sql = "\n".join(inventory_lines)

# Returns / refunds
returns_lines = [
    "INSERT INTO ecommerce.returns (return_id, order_id, customer_id, return_reason, status, created_at, approved_at, resolved_at) VALUES"
]
refund_lines = [
    "INSERT INTO ecommerce.refunds (refund_id, order_id, customer_id, refund_amount, status, reason, created_at, resolved_at) VALUES"
]
return_id = 1
refund_id = 1
for order_id in range(1, 2000):
    if random.random() < 0.18:
        reason = random.choice(["Damaged item", "Wrong item", "Changed mind", "Late delivery"])
        created = datetime(2026, 1, 1) + timedelta(days=random.randint(0, 300), hours=random.randint(0, 23))
        approved = created + timedelta(days=1)
        resolved = approved + timedelta(days=random.randint(1, 5))
        status = random.choice(["pending", "approved", "rejected", "completed"])
        returns_lines.append(f"({return_id}, {order_id}, {random.randint(1, customer_count)}, '{reason}', '{status}', '{created.strftime('%Y-%m-%d %H:%M:%S')}', '{approved.strftime('%Y-%m-%d %H:%M:%S')}', '{resolved.strftime('%Y-%m-%d %H:%M:%S')}')")
        return_id += 1

        refund_amount = round(random.uniform(25, 250), 2)
        refund_lines.append(f"({refund_id}, {order_id}, {random.randint(1, customer_count)}, {refund_amount}, 'completed', '{reason}', '{created.strftime('%Y-%m-%d %H:%M:%S')}', '{resolved.strftime('%Y-%m-%d %H:%M:%S')}')")
        refund_id += 1

if returns_lines[-1].startswith("INSERT"):
    returns_sql = "\n".join(returns_lines) + ";"
else:
    returns_sql = "\n".join(returns_lines) + ";"
if refund_lines[-1].startswith("INSERT"):
    refunds_sql = "\n".join(refund_lines) + ";"
else:
    refunds_sql = "\n".join(refund_lines) + ";"

# Shipments
shipment_lines = [
    "INSERT INTO ecommerce.shipments (shipment_id, order_id, carrier, tracking_number, shipped_at, delivered_at, status) VALUES"
]
for shipment_id in range(1, min(order_count, 3000) + 1):
    order_id = shipment_id
    carrier = random.choice(["FedEx", "UPS", "DHL", "USPS"])
    tracking = f"{carrier[:2].upper()}{random.randint(100000, 999999)}"
    shipped = datetime(2026, 1, 1) + timedelta(days=random.randint(0, 300), hours=random.randint(0, 23))
    delivered = shipped + timedelta(days=random.randint(1, 8)) if random.random() < 0.7 else None
    status = "delivered" if delivered else "in_transit"
    if delivered:
        shipment_lines.append(f"({shipment_id}, {order_id}, '{carrier}', '{tracking}', '{shipped.strftime('%Y-%m-%d %H:%M:%S')}', '{delivered.strftime('%Y-%m-%d %H:%M:%S')}', '{status}')")
    else:
        shipment_lines.append(f"({shipment_id}, {order_id}, '{carrier}', '{tracking}', '{shipped.strftime('%Y-%m-%d %H:%M:%S')}', NULL, '{status}')")
shipment_lines[-1] += ";"
shipments_sql = "\n".join(shipment_lines)

full_script = "\n\n".join([
    "CREATE SCHEMA IF NOT EXISTS ecommerce;",
    customer_sql,
    product_sql,
    order_sql,
    items_sql,
    inventory_sql,
    returns_sql,
    refunds_sql,
    shipments_sql,
])

OUTPUT.write_text(full_script + "\n", encoding="utf-8")
print(f"Generated realistic seed dataset with {customer_count} customers and {order_count} orders at {OUTPUT}")
