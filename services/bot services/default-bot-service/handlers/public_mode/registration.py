"""Public mode registration handlers."""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)

def start_registration(session_id: str, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """Start user registration process"""
    try:
        response = {
            "message": "Welcome! Let's get you registered. What type of account would you like to create?",
            "registration_options": [
                {"id": "msme", "name": "MSME Account", "description": "For small and medium businesses"},
                {"id": "affiliate", "name": "Affiliate Account", "description": "For marketing partners and affiliates"},
                {"id": "customer", "name": "Customer Account", "description": "For regular customers"}
            ],
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Registration started for session {session_id}")
        return response
        
    except Exception as e:
        logger.error(f"Error starting registration: {e}")
        return {"error": f"Failed to start registration: {str(e)}"}

def choose_user_type(session_id: str, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """Handle user type selection"""
    try:
        user_type = payload.get("data", {}).get("user_type")
        if not user_type:
            return {"error": "User type is required"}
        
        valid_types = ["msme", "affiliate", "customer"]
        if user_type not in valid_types:
            return {"error": "Invalid user type selected"}
        
        response = {
            "message": f"Great! You selected {user_type} account. Let's gather some information.",
            "user_type": user_type,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"User type {user_type} selected for session {session_id}")
        return response
        
    except Exception as e:
        logger.error(f"Error choosing user type: {e}")
        return {"error": f"Failed to choose user type: {str(e)}"}

def affiliate_flow(session_id: str, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """Handle affiliate registration flow"""
    try:
        response = {
            "message": "Affiliate registration - Please provide your details:",
            "required_fields": [
                "full_name",
                "email",
                "phone",
                "business_name",
                "referral_source",
                "expected_monthly_referrals"
            ],
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Affiliate flow started for session {session_id}")
        return response
        
    except Exception as e:
        logger.error(f"Error in affiliate flow: {e}")
        return {"error": f"Failed to start affiliate flow: {str(e)}"}

def msme_flow(session_id: str, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """Handle MSME registration flow"""
    try:
        response = {
            "message": "MSME registration - Please provide your business details:",
            "required_fields": [
                "business_name",
                "business_type",
                "registration_number",
                "owner_name",
                "email",
                "phone",
                "business_address",
                "years_in_business"
            ],
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"MSME flow started for session {session_id}")
        return response
        
    except Exception as e:
        logger.error(f"Error in MSME flow: {e}")
        return {"error": f"Failed to start MSME flow: {str(e)}"}

def collect_personal_info(session_id: str, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """Collect personal information"""
    try:
        full_name = payload.get("data", {}).get("full_name")
        email = payload.get("data", {}).get("email")
        phone = payload.get("data", {}).get("phone")
        
        if not all([full_name, email, phone]):
            return {"error": "Full name, email, and phone are required"}
        
        # Basic email validation
        if "@" not in email:
            return {"error": "Please enter a valid email address"}
        
        response = {
            "message": "Personal information collected successfully",
            "personal_info": {
                "full_name": full_name,
                "email": email,
                "phone": phone
            },
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Personal info collected for session {session_id}: {full_name}")
        return response
        
    except Exception as e:
        logger.error(f"Error collecting personal info: {e}")
        return {"error": f"Failed to collect personal info: {str(e)}"}

def collect_business_info(session_id: str, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """Collect business information for MSME"""
    try:
        business_name = payload.get("data", {}).get("business_name")
        business_type = payload.get("data", {}).get("business_type")
        registration_number = payload.get("data", {}).get("registration_number")
        
        if not all([business_name, business_type, registration_number]):
            return {"error": "Business name, type, and registration number are required"}
        
        response = {
            "message": "Business information collected successfully",
            "business_info": {
                "business_name": business_name,
                "business_type": business_type,
                "registration_number": registration_number
            },
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Business info collected for session {session_id}: {business_name}")
        return response
        
    except Exception as e:
        logger.error(f"Error collecting business info: {e}")
        return {"error": f"Failed to collect business info: {str(e)}"}

def collect_affiliate_info(session_id: str, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """Collect affiliate-specific information"""
    try:
        referral_source = payload.get("data", {}).get("referral_source")
        expected_referrals = payload.get("data", {}).get("expected_monthly_referrals")
        
        if not all([referral_source, expected_referrals]):
            return {"error": "Referral source and expected referrals are required"}
        
        response = {
            "message": "Affiliate information collected successfully",
            "affiliate_info": {
                "referral_source": referral_source,
                "expected_monthly_referrals": expected_referrals
            },
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Affiliate info collected for session {session_id}: {referral_source}")
        return response
        
    except Exception as e:
        logger.error(f"Error collecting affiliate info: {e}")
        return {"error": f"Failed to collect affiliate info: {str(e)}"}

def validate_registration_data(session_id: str, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """Validate all registration data"""
    try:
        registration_data = payload.get("data", {}).get("registration_data", {})
        
        # Mock validation - in real implementation, this would validate against business rules
        validation_results = {
            "personal_info_valid": True,
            "business_info_valid": True,
            "contact_info_valid": True,
            "all_valid": True
        }
        
        response = {
            "message": "Registration data validated successfully",
            "validation_results": validation_results,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Registration data validated for session {session_id}")
        return response
        
    except Exception as e:
        logger.error(f"Error validating registration data: {e}")
        return {"error": f"Failed to validate registration data: {str(e)}"}

def create_user_account(session_id: str, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """Create user account in system"""
    try:
        user_data = payload.get("data", {}).get("user_data", {})
        user_type = user_data.get("user_type")
        
        if not user_type:
            return {"error": "User type is required"}
        
        # Generate user ID
        user_id = f"USER-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
        
        # Mock account creation - in real implementation, this would create in database
        account = {
            "user_id": user_id,
            "user_type": user_type,
            "status": "pending_verification",
            "created_at": datetime.now().isoformat(),
            "session_id": session_id
        }
        
        response = {
            "message": f"Account created successfully! User ID: {user_id}",
            "account": account,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"User account created for session {session_id}: {user_id}")
        return response
        
    except Exception as e:
        logger.error(f"Error creating user account: {e}")
        return {"error": f"Failed to create user account: {str(e)}"}

def send_verification_email(session_id: str, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """Send verification email to user"""
    try:
        email = payload.get("data", {}).get("email")
        user_id = payload.get("data", {}).get("user_id")
        
        if not email or not user_id:
            return {"error": "Email and user ID are required"}
        
        # Mock email sending - in real implementation, this would send actual email
        verification_code = str(uuid.uuid4())[:6].upper()
        
        response = {
            "message": f"Verification email sent to {email}",
            "verification_code": verification_code,
            "email": email,
            "user_id": user_id,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Verification email sent for session {session_id}: {email}")
        return response
        
    except Exception as e:
        logger.error(f"Error sending verification email: {e}")
        return {"error": f"Failed to send verification email: {str(e)}"}

def verify_email_code(session_id: str, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """Verify email verification code"""
    try:
        provided_code = payload.get("data", {}).get("verification_code")
        expected_code = payload.get("data", {}).get("expected_code")
        
        if not provided_code or not expected_code:
            return {"error": "Verification code is required"}
        
        if provided_code != expected_code:
            return {"error": "Invalid verification code"}
        
        response = {
            "message": "Email verified successfully!",
            "verified": True,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Email verified for session {session_id}")
        return response
        
    except Exception as e:
        logger.error(f"Error verifying email code: {e}")
        return {"error": f"Failed to verify email code: {str(e)}"}

def complete_registration(session_id: str, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """Complete the registration process"""
    try:
        user_id = payload.get("data", {}).get("user_id")
        user_type = payload.get("data", {}).get("user_type")
        
        if not user_id or not user_type:
            return {"error": "User ID and type are required"}
        
        # Mock registration completion - in real implementation, this would update database
        registration_complete = {
            "user_id": user_id,
            "user_type": user_type,
            "status": "active",
            "completed_at": datetime.now().isoformat(),
            "session_id": session_id
        }
        
        response = {
            "message": f"Registration completed successfully! Welcome to our platform as a {user_type}.",
            "registration": registration_complete,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Registration completed for session {session_id}: {user_id} ({user_type})")
        return response
        
    except Exception as e:
        logger.error(f"Error completing registration: {e}")
        return {"error": f"Failed to complete registration: {str(e)}"}

def authenticate_user(session_id: str, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """Authenticate existing user"""
    try:
        email = payload.get("data", {}).get("email")
        password = payload.get("data", {}).get("password")
        
        if not email or not password:
            return {"error": "Email and password are required"}
        
        # Mock authentication - in real implementation, this would verify credentials
        user_id = f"USER-{str(uuid.uuid4())[:8].upper()}"
        
        response = {
            "message": "Authentication successful!",
            "user_id": user_id,
            "email": email,
            "authenticated": True,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"User authenticated for session {session_id}: {email}")
        return response
        
    except Exception as e:
        logger.error(f"Error authenticating user: {e}")
        return {"error": f"Failed to authenticate user: {str(e)}"}