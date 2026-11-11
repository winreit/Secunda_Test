from app.messaging.broker import broker


async def publish_payment_event(payload: dict) -> None:
    await broker.publish(message=payload, queue="payments.new", persist=True)
