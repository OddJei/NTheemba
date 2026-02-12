"""
Simulation: Bot Session and User-Bot Session Workflow

This script demonstrates the complete workflow of:
1. Creating a bot session
2. Creating a user-bot session
3. Managing session lifecycle

Run with:
  python -m scripts.simulate_session_workflow

Or from the ICE-service root:
  python scripts/simulate_session_workflow.py

Make sure bot-session Docker container is running:
  docker-compose up -d bot-session
"""
import asyncio
import logging
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(__file__).split('scripts')[0])

from app.config import Config
from app.adapters.factory import AdapterFactory
from app.adapters.auth import AuthenticationAdapter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SessionWorkflowSimulation:
    """Simulates the bot session and user-bot session workflow."""
    
    def __init__(self):
        self.bot_session_adapter = AdapterFactory.get_bot_session_adapter()
        self.user_bot_adapter = AdapterFactory.get_user_bot_session_adapter()
        self.auth_adapter = AuthenticationAdapter()
    
    async def run(self):
        """Run the complete simulation."""
        logger.info("="*70)
        logger.info("ICE SERVICE SIMULATION: Bot Session & User-Bot Session Workflow")
        logger.info("="*70)
        
        # Log configuration
        Config.log_config()
        
        try:
            # Step 1: Health checks
            await self._step_1_health_checks()
            
            # Step 2: Authenticate user
            await self._step_2_authenticate_user()
            
            # Step 3: Create bot session
            await self._step_3_create_bot_session()
            
            # Step 4: Create user-bot session
            await self._step_4_create_user_bot_session()
            
            # Step 5: Query active sessions
            await self._step_5_query_active_sessions()
            
            # Step 6: Close user-bot session
            await self._step_6_close_user_bot_session()
            
            # Step 7: Reactivate session
            await self._step_7_reactivate_session()
            
            logger.info("="*70)
            logger.info("SIMULATION COMPLETED SUCCESSFULLY!")
            logger.info("="*70)
            
        except Exception as e:
            logger.error(f"Simulation failed: {e}", exc_info=True)
        
        finally:
            await self._cleanup()
    
    async def _step_1_health_checks(self):
        """Step 1: Check health of services."""
        logger.info("\n[STEP 1] Health Checks")
        logger.info("-" * 70)
        
        # Check bot-session
        logger.info("Checking bot-session service...")
        bot_session_healthy = await self.bot_session_adapter.health_check()
        logger.info(f"  Bot-session health: {bot_session_healthy}")
        
        if not bot_session_healthy:
            raise Exception(
                f"Bot-session service is not healthy at {Config.BOT_SESSION_URL}\n"
                "Make sure to run: docker-compose up -d bot-session"
            )
        
        # Check MSME engine
        logger.info("Checking MSME Engine service...")
        msme_healthy = await self.auth_adapter.health_check()
        logger.info(f"  MSME Engine health: {msme_healthy}")
        
        if not msme_healthy:
            logger.warning(
                f"MSME Engine is not healthy at {Config.MSME_ENGINE_URL}\n"
                "Some steps will be skipped."
            )
    
    async def _step_2_authenticate_user(self):
        """Step 2: Authenticate user."""
        logger.info("\n[STEP 2] Authenticate User")
        logger.info("-" * 70)
        
        phone_number = "260701234567"
        logger.info(f"Verifying user: {phone_number}")
        
        user_info = await self.auth_adapter.verify_user(phone_number)
        if user_info:
            logger.info(f"  User verified:")
            logger.info(f"    Role: {user_info.get('role')}")
            logger.info(f"    Status: {user_info.get('status')}")
            if user_info.get('business_id'):
                logger.info(f"    Business ID: {user_info.get('business_id')}")
        else:
            logger.info(f"  User not found (or MSME Engine offline)")
    
    async def _step_3_create_bot_session(self):
        """Step 3: Create bot session."""
        logger.info("\n[STEP 3] Create Bot Session")
        logger.info("-" * 70)
        
        logger.info("Creating bot session structure...")
        
        # In a real scenario, bot sessions are typically managed by the bot service
        # Here we just verify the infrastructure adapter can access the service
        logger.info("  Bot-session infrastructure adapter is ready")
        logger.info("  (Bot sessions are typically created by bot services)")
    
    async def _step_4_create_user_bot_session(self):
        """Step 4: Create user-bot session."""
        logger.info("\n[STEP 4] Create User-Bot Session")
        logger.info("-" * 70)
        
        phone_number = "260701234567"
        business_id = "BIZ-TEST-001"
        
        metadata = {
            "platform": "whatsapp",
            "bot_phone": "260709999999",
            "affiliate_id": "aff-sim-001",
            "entry_point": "whatsapp_broadcast"
        }
        
        logger.info(f"Creating session for user: {phone_number}")
        logger.info(f"  Business ID: {business_id}")
        logger.info(f"  Platform: {metadata['platform']}")
        logger.info(f"  Bot Phone: {metadata['bot_phone']}")
        
        try:
            session = await self.user_bot_adapter.create_session(
                phone_number, 
                business_id, 
                metadata
            )
            
            self.session_id = session.get("session_id")
            logger.info(f"✓ Session created successfully!")
            logger.info(f"  Session ID: {self.session_id}")
            logger.info(f"  Status: {session.get('status')}")
            logger.info(f"  State: {session.get('state')}")
            logger.info(f"  Session Mode: {session.get('session_mode')}")
            logger.info(f"  Created At: {session.get('created_at')}")
            
        except Exception as e:
            logger.error(f"✗ Failed to create session: {e}")
            raise
    
    async def _step_5_query_active_sessions(self):
        """Step 5: Query active sessions."""
        logger.info("\n[STEP 5] Query Active Sessions")
        logger.info("-" * 70)
        
        phone_number = "260701234567"
        logger.info(f"Getting active sessions for: {phone_number}")
        
        try:
            active_sessions = await self.user_bot_adapter.get_active_sessions(phone_number)
            
            logger.info(f"✓ Found {len(active_sessions)} active sessions")
            for i, sess in enumerate(active_sessions, 1):
                logger.info(f"  Session {i}:")
                logger.info(f"    ID: {sess.get('id')}")
                logger.info(f"    Status: {sess.get('status')}")
                logger.info(f"    Mode: {sess.get('session_mode')}")
            
        except Exception as e:
            logger.error(f"✗ Failed to query sessions: {e}")
    
    async def _step_6_close_user_bot_session(self):
        """Step 6: Close user-bot session."""
        logger.info("\n[STEP 6] Close User-Bot Session")
        logger.info("-" * 70)
        
        if not hasattr(self, 'session_id'):
            logger.info("  No session to close (session creation failed)")
            return
        
        logger.info(f"Closing session: {self.session_id}")
        
        try:
            closed = await self.user_bot_adapter.close_session(
                self.session_id, 
                "simulation_complete"
            )
            
            if closed:
                logger.info(f"✓ Session closed successfully!")
                
                # Verify session is closed
                state = await self.user_bot_adapter.get_session_state(self.session_id)
                if state:
                    logger.info(f"  Updated Status: {state.get('status')}")
            else:
                logger.error(f"✗ Failed to close session")
                
        except Exception as e:
            logger.error(f"✗ Error closing session: {e}")
    
    async def _step_7_reactivate_session(self):
        """Step 7: Reactivate session."""
        logger.info("\n[STEP 7] Reactivate Session")
        logger.info("-" * 70)
        
        phone_number = "260701234567"
        business_id = "BIZ-TEST-001"
        
        metadata = {
            "platform": "whatsapp",
            "bot_phone": "260709999999",
            "affiliate_id": "aff-sim-002"
        }
        
        logger.info(f"Reactivating session for: {phone_number}")
        
        try:
            session = await self.user_bot_adapter.create_session(
                phone_number, 
                business_id, 
                metadata
            )
            
            is_reactivated = session.get("reactivated", False)
            self.session_id = session.get("session_id")
            
            if is_reactivated:
                logger.info(f"✓ Session reactivated!")
                logger.info(f"  Session ID: {self.session_id}")
                logger.info(f"  Status: {session.get('status')}")
                logger.info(f"  Reactivated: {is_reactivated}")
            else:
                logger.info(f"✓ New session created")
                logger.info(f"  Session ID: {self.session_id}")
                logger.info(f"  Status: {session.get('status')}")
            
        except Exception as e:
            logger.error(f"✗ Failed to reactivate session: {e}")
    
    async def _cleanup(self):
        """Cleanup resources."""
        logger.info("\n[CLEANUP] Closing adapters...")
        await AdapterFactory.cleanup()
        await self.auth_adapter.close()
        logger.info("✓ Cleanup complete")


async def main():
    """Main entry point."""
    simulation = SessionWorkflowSimulation()
    await simulation.run()


if __name__ == "__main__":
    asyncio.run(main())
