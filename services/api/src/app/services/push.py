import asyncio
import uuid

from exponent_server_sdk import (
    DeviceNotRegisteredError,
    PushClient,
    PushMessage,
)
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.listing import Listing
from app.models.user import PushToken


async def send_push_for_matches(
    user_matches: dict[uuid.UUID, list[Listing]],
    db: AsyncSession,
) -> None:
    """Send Expo Push notifications to users with matching listings."""
    if not user_matches:
        return

    push_client = PushClient()

    for user_id, listings in user_matches.items():
        result = await db.execute(select(PushToken).where(PushToken.user_id == user_id))
        tokens = result.scalars().all()

        if not tokens:
            continue

        count = len(listings)
        title = "New listings found!"
        body = f"{count} new {'listing' if count == 1 else 'listings'} matching your filters"

        messages = [
            PushMessage(to=token.expo_push_token, title=title, body=body, data={"count": count}) for token in tokens
        ]

        try:
            responses = await asyncio.to_thread(push_client.publish_multiple, messages)
            for i, response in enumerate(responses):
                try:
                    response.validate_response()
                except DeviceNotRegisteredError:
                    logger.warning(f"Removing unregistered push token: {tokens[i].expo_push_token}")
                    await db.delete(tokens[i])
        except Exception:
            logger.exception(f"Failed to send push notifications to user {user_id}")

    await db.commit()
