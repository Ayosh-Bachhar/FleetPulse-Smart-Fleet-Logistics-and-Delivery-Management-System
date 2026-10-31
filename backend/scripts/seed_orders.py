import asyncio

from app.database.connection import (
    connect_to_database,
    close_database_connection,
)
from app.models.order import Order, OrderStatus
from app.models.user import User, Role


SAMPLE_ORDERS = [
    {
        "reference_code": "FP-DEMO-ORDER-001",
        "pickup_address": "Uttara, Dhaka",
        "delivery_address": "Mirpur, Dhaka",
        "weight_kg": 200,
        "length_cm": 100,
        "width_cm": 50,
        "height_cm": 50,
        "volume_m3": 0.25,
        "is_rush": False,
    },
    {
        "reference_code": "FP-DEMO-ORDER-002",
        "pickup_address": "Banani, Dhaka",
        "delivery_address": "Dhanmondi, Dhaka",
        "weight_kg": 150,
        "length_cm": 120,
        "width_cm": 80,
        "height_cm": 70,
        "volume_m3": 0.672,
        "is_rush": True,
    },
    {
        "reference_code": "FP-DEMO-ORDER-003",
        "pickup_address": "Mohakhali, Dhaka",
        "delivery_address": "Gulshan, Dhaka",
        "weight_kg": 75,
        "length_cm": 50,
        "width_cm": 40,
        "height_cm": 30,
        "volume_m3": 0.06,
        "is_rush": False,
    },
]


async def seed_orders():
    await connect_to_database()

    try:
        customer = await User.find_one(
            User.role == Role.CUSTOMER
        )

        if customer is None:
            print(
                "No Customer account found. "
                "Register a Customer before seeding orders."
            )
            return

        for item in SAMPLE_ORDERS:
            existing = await Order.find_one(
                Order.reference_code == item["reference_code"]
            )

            if existing is not None:
                print(
                    "Already exists:",
                    item["reference_code"],
                )
                continue

            order = Order(
                **item,
                customer_id=customer.id,
                status=OrderStatus.WAREHOUSE,
            )

            await order.insert()

            print("Created:", item["reference_code"])

        print("Demo-order seeding finished.")

    finally:
        await close_database_connection()


if __name__ == "__main__":
    asyncio.run(seed_orders())