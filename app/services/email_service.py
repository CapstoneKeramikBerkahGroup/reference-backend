from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from app.core.config import settings
import random
import string
from typing import Dict


def get_mail_config():
    """
    Get dynamic email configuration based on selected provider
    Supports: Gmail, Office365 (ac.id domain)
    """
    return ConnectionConfig(
        MAIL_USERNAME=settings.MAIL_USERNAME,
        MAIL_PASSWORD=settings.MAIL_PASSWORD,
        MAIL_FROM=settings.MAIL_FROM,
        MAIL_PORT=settings.MAIL_PORT,
        MAIL_SERVER=settings.MAIL_SERVER,
        MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
        MAIL_STARTTLS=settings.MAIL_STARTTLS,
        MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
        USE_CREDENTIALS=settings.USE_CREDENTIALS,
        VALIDATE_CERTS=settings.VALIDATE_CERTS
    )


# Initialize FastMail with dynamic configuration
fm = FastMail(get_mail_config())


def generate_verification_code(length: int = 6) -> str:
    """Generate random verification code"""
    return ''.join(random.choices(string.digits, k=length))


async def send_verification_email(email: str, code: str, name: str = "User"):
    """Send verification code email for password reset"""
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .container {{
                background-color: #f9f9f9;
                border-radius: 10px;
                padding: 30px;
                border: 1px solid #ddd;
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                border-radius: 10px 10px 0 0;
                text-align: center;
            }}
            .code-box {{
                background-color: #667eea;
                color: white;
                font-size: 32px;
                font-weight: bold;
                letter-spacing: 8px;
                padding: 20px;
                text-align: center;
                border-radius: 8px;
                margin: 20px 0;
            }}
            .footer {{
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #ddd;
                font-size: 12px;
                color: #888;
                text-align: center;
            }}
            .warning {{
                background-color: #fff3cd;
                border: 1px solid #ffc107;
                color: #856404;
                padding: 15px;
                border-radius: 5px;
                margin: 15px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔐 Password Reset Request</h1>
            </div>
            <div style="padding: 20px;">
                <p>Hello <strong>{name}</strong>,</p>
                
                <p>We received a request to reset your password for your <strong>Reference Management System</strong> account.</p>
                
                <p>Your verification code is:</p>
                
                <div class="code-box">
                    {code}
                </div>
                
                <p>This code will expire in <strong>{settings.VERIFICATION_CODE_EXPIRE_MINUTES} minutes</strong>.</p>
                
                <div class="warning">
                    <strong>⚠️ Security Notice:</strong><br>
                    If you did not request a password reset, please ignore this email or contact support if you have concerns.
                </div>
                
                <p>Best regards,<br>
                <strong>Reference Management System Team</strong></p>
            </div>
            <div class="footer">
                <p>This is an automated email sent via <strong>{settings.MAIL_PROVIDER.upper()}</strong>. Please do not reply to this message.</p>
                <p>&copy; 2025 Reference Management System. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    message = MessageSchema(
        subject="Password Reset Verification Code",
        recipients=[email],
        body=html_body,
        subtype=MessageType.html
    )
    
    try:
        await fm.send_message(message)
        print(f"✅ Verification email sent to {email} via {settings.MAIL_PROVIDER}")
    except Exception as e:
        print(f"⚠️ Failed to send email via {settings.MAIL_PROVIDER}: {str(e)}")
        if settings.DEBUG:
            print(f"🔑 DEVELOPMENT MODE - Verification Code: {code}")
        raise


async def send_password_changed_notification(email: str, name: str = "User"):
    """Send notification email when password is successfully changed"""
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .container {{
                background-color: #f9f9f9;
                border-radius: 10px;
                padding: 30px;
                border: 1px solid #ddd;
            }}
            .header {{
                background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
                color: white;
                padding: 20px;
                border-radius: 10px 10px 0 0;
                text-align: center;
            }}
            .success-icon {{
                font-size: 48px;
                text-align: center;
                margin: 20px 0;
            }}
            .footer {{
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #ddd;
                font-size: 12px;
                color: #888;
                text-align: center;
            }}
            .warning {{
                background-color: #fff3cd;
                border: 1px solid #ffc107;
                color: #856404;
                padding: 15px;
                border-radius: 5px;
                margin: 15px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>✅ Password Changed Successfully</h1>
            </div>
            <div style="padding: 20px;">
                <div class="success-icon">🎉</div>
                
                <p>Hello <strong>{name}</strong>,</p>
                
                <p>This is to confirm that your password has been <strong>successfully changed</strong> for your Reference Management System account.</p>
                
                <p>You can now log in with your new password.</p>
                
                <div class="warning">
                    <strong>⚠️ Security Alert:</strong><br>
                    If you did not make this change, please contact our support team immediately and secure your account.
                </div>
                
                <p>Best regards,<br>
                <strong>Reference Management System Team</strong></p>
            </div>
            <div class="footer">
                <p>This is an automated email sent via <strong>{settings.MAIL_PROVIDER.upper()}</strong>. Please do not reply to this message.</p>
                <p>&copy; 2025 Reference Management System. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    message = MessageSchema(
        subject="Password Changed Successfully",
        recipients=[email],
        body=html_body,
        subtype=MessageType.html
    )
    
    try:
        await fm.send_message(message)
        print(f"✅ Password change notification sent to {email} via {settings.MAIL_PROVIDER}")
    except Exception as e:
        print(f"⚠️ Failed to send notification via {settings.MAIL_PROVIDER}: {str(e)}")
        # Don't raise error for notification emails
        pass
