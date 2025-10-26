"""Notification service API client."""

import logging
import requests
from typing import Dict, Any, List, Optional
from config.environment import config

logger = logging.getLogger(__name__)

class NotificationServiceClient:
    """Client for notification service"""
    
    def __init__(self):
        self.base_url = config.get_service_url("NOTIFICATION_SERVICE")
        self.timeout = config.get_service_timeout("NOTIFICATION_SERVICE")
        self.api_key = config.get("API_KEY_VALUE")
    
    def _make_request(self, method: str, endpoint: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make HTTP request to notification service"""
        try:
            url = f"{self.base_url}{endpoint}"
            headers = {
                "Content-Type": "application/json",
                config.get("API_KEY_HEADER"): self.api_key
            }
            
            response = requests.request(
                method=method,
                url=url,
                json=data,
                headers=headers,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Notification service request failed: {e}")
            return {"error": f"Notification service error: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error in notification service: {e}")
            return {"error": f"Unexpected error: {str(e)}"}
    
    def send_whatsapp_message(self, phone_number: str, message: str, template: str = None) -> Dict[str, Any]:
        """Send WhatsApp message"""
        try:
            data = {
                "phone_number": phone_number,
                "message": message,
                "template": template
            }
            
            result = self._make_request("POST", "/notifications/whatsapp", data)
            
            if "error" not in result:
                logger.info(f"WhatsApp message sent to: {phone_number}")
            else:
                logger.warning(f"Failed to send WhatsApp message to: {phone_number}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error sending WhatsApp message: {e}")
            return {"error": f"WhatsApp message error: {str(e)}"}
    
    def send_sms(self, phone_number: str, message: str) -> Dict[str, Any]:
        """Send SMS message"""
        try:
            data = {
                "phone_number": phone_number,
                "message": message
            }
            
            result = self._make_request("POST", "/notifications/sms", data)
            
            if "error" not in result:
                logger.info(f"SMS sent to: {phone_number}")
            else:
                logger.warning(f"Failed to send SMS to: {phone_number}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error sending SMS: {e}")
            return {"error": f"SMS error: {str(e)}"}
    
    def send_email(self, email: str, subject: str, message: str, template: str = None) -> Dict[str, Any]:
        """Send email notification"""
        try:
            data = {
                "email": email,
                "subject": subject,
                "message": message,
                "template": template
            }
            
            result = self._make_request("POST", "/notifications/email", data)
            
            if "error" not in result:
                logger.info(f"Email sent to: {email}")
            else:
                logger.warning(f"Failed to send email to: {email}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return {"error": f"Email error: {str(e)}"}
    
    def send_push_notification(self, user_id: str, title: str, message: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send push notification"""
        try:
            payload = {
                "user_id": user_id,
                "title": title,
                "message": message,
                "data": data or {}
            }
            
            result = self._make_request("POST", "/notifications/push", payload)
            
            if "error" not in result:
                logger.info(f"Push notification sent to user: {user_id}")
            else:
                logger.warning(f"Failed to send push notification to user: {user_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error sending push notification: {e}")
            return {"error": f"Push notification error: {str(e)}"}
    
    def send_bulk_notification(self, recipients: List[Dict[str, Any]], message: str, channel: str) -> Dict[str, Any]:
        """Send bulk notification to multiple recipients"""
        try:
            data = {
                "recipients": recipients,
                "message": message,
                "channel": channel
            }
            
            result = self._make_request("POST", "/notifications/bulk", data)
            
            if "error" not in result:
                logger.info(f"Bulk notification sent to {len(recipients)} recipients via {channel}")
            else:
                logger.warning(f"Failed to send bulk notification to {len(recipients)} recipients")
            
            return result
            
        except Exception as e:
            logger.error(f"Error sending bulk notification: {e}")
            return {"error": f"Bulk notification error: {str(e)}"}
    
    def get_notification_status(self, notification_id: str) -> Dict[str, Any]:
        """Get notification delivery status"""
        try:
            result = self._make_request("GET", f"/notifications/{notification_id}/status")
            
            if "error" not in result:
                logger.info(f"Notification status retrieved: {notification_id}")
            else:
                logger.warning(f"Failed to get notification status: {notification_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting notification status: {e}")
            return {"error": f"Notification status error: {str(e)}"}
    
    def get_notification_history(self, user_id: str = None, limit: int = 100) -> Dict[str, Any]:
        """Get notification history"""
        try:
            params = {"limit": limit}
            if user_id:
                params["user_id"] = user_id
            
            result = self._make_request("GET", "/notifications/history", params)
            
            if "error" not in result:
                logger.info(f"Notification history retrieved for user: {user_id}")
            else:
                logger.warning(f"Failed to get notification history for user: {user_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting notification history: {e}")
            return {"error": f"Notification history error: {str(e)}"}
    
    def create_notification_template(self, template_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create notification template"""
        try:
            result = self._make_request("POST", "/notifications/templates", template_data)
            
            if "error" not in result:
                logger.info("Notification template created")
            else:
                logger.warning("Failed to create notification template")
            
            return result
            
        except Exception as e:
            logger.error(f"Error creating notification template: {e}")
            return {"error": f"Template creation error: {str(e)}"}
    
    def get_notification_templates(self) -> Dict[str, Any]:
        """Get available notification templates"""
        try:
            result = self._make_request("GET", "/notifications/templates")
            
            if "error" not in result:
                logger.info("Notification templates retrieved")
            else:
                logger.warning("Failed to get notification templates")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting notification templates: {e}")
            return {"error": f"Template retrieval error: {str(e)}"}
    
    def schedule_notification(self, notification_data: Dict[str, Any], schedule_time: str) -> Dict[str, Any]:
        """Schedule notification for later delivery"""
        try:
            data = {
                "notification": notification_data,
                "schedule_time": schedule_time
            }
            
            result = self._make_request("POST", "/notifications/schedule", data)
            
            if "error" not in result:
                logger.info(f"Notification scheduled for: {schedule_time}")
            else:
                logger.warning(f"Failed to schedule notification for: {schedule_time}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error scheduling notification: {e}")
            return {"error": f"Notification scheduling error: {str(e)}"}