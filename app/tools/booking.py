from langchain_core.tools import tool

@tool
async def reschedule_booking(booking_id: int, new_datetime: str) -> str:
    """
    Reschedule an existing trial class to a new date and time.
    Use this when a user wants to change their appointment time.
    """
    try:
        # 1. Update your PostgreSQL database (Pseudo-code for your DB logic)
        # await db.execute("UPDATE bookings SET datetime = $1 WHERE id = $2", new_datetime, booking_id)
        
        # 2. Update Google Calendar (Pseudo-code for your Calendar logic)
        # calendar_service.events().patch(calendarId='primary', eventId=booking_id, body={'start': {'dateTime': new_datetime}}).execute()
        
        return f"Successfully rescheduled booking #{booking_id} to {new_datetime}. Please confirm the new time with the parent."
    except Exception as e:
        return f"Failed to reschedule: {str(e)}. Ask the user to try again or request a human."