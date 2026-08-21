import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import secrets
import logging
from app.config import settings
from app.db.redis_client import _redis_async

logger = logging.getLogger(__name__)

async def send_reset_link_email(request_url: str) -> bool:
    """Generates a secure token, saves to Redis, and emails the reset button."""
    # 1. Generate a highly secure random 32-character URL token
    token = secrets.token_urlsafe(32)
    admin_email = settings.admin_recovery_email
    
    # 2. Save token to Redis with a 15-minute expiration (900 seconds)
    if _redis_async:
        await _redis_async.setex(f"reset_token:{token}", 900, "admin_user")
    else:
        logger.error("Redis is not connected. Cannot store reset token.")
        return False

    # 3. Construct the HTML Email with the Blue Button
    # We use request_url to dynamically get your local or Render domain
    reset_link = f"{request_url}/reset-password?token={token}"
    
    msg = MIMEMultipart('alternative')
    msg['From'] = settings.smtp_email
    msg['To'] = admin_email
    msg['Subject'] = "🔒 Swesh Dashboard - Password Reset Request"

    # HTML structure matching your preferred design
    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6; max-width: 600px; margin: 0 auto; padding: 20px;">
        <p>Thanks for requesting a password reset. To create a new password, just use the button below.</p>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{reset_link}" 
               style="background-color: #0079D3; color: white; padding: 12px 24px; text-decoration: none; font-weight: bold; border-radius: 4px; display: inline-block;">
               Reset Password
            </a>
        </div>
        
        <p>If you didn't make this request, you can ignore this email and carry on as usual. If you need any more help logging in, contact support.</p>
      </body>
    </html>
    """
    
    msg.attach(MIMEText(html_body, 'html'))

    # 4. Send the Email via Gmail SMTP
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(settings.smtp_email, settings.smtp_password)
        server.sendmail(settings.smtp_email, admin_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        logger.error(f"Failed to send reset email: {e}")
        return False