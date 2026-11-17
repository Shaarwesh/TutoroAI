
"""Legacy booking tool compatibility."""

from langchain_core.tools import tool


@tool
async def reschedule_booking(
    booking_id: int,
    new_datetime: str,
) -> str:
    """
    Handle legacy rescheduling requests safely.

    Does not change the booking until a
    verified rescheduling workflow exists.
    """
    return (
        f"Rescheduling request for booking "
        f"#{booking_id} to {new_datetime} "
        "has not been completed. "
        "The original booking remains unchanged. "
        "Please contact the administrator."
    )
