"""
Adapter factory for creating adapter instances with proper configuration.

This module provides a clean interface for creating adapters with real
service URLs from environment configuration.
"""
import logging
from typing import Optional
from app.config import Config
from app.adapters.bot_session import BotSessionServiceAdapter
from app.adapters.user_bot_session import UserBotConversationAdapter
from app.adapters.cart_order import CartOrderServiceAdapter
from app.adapters.delivery import DeliveryServiceAdapter
from app.adapters.payment import PaymentRevenueAdapter
from app.adapters.catalog import CatalogInventoryAdapter
from app.adapters.msme import MsmeEngineAdapter
from app.adapters.affiliate import AffiliateEngineAdapter

logger = logging.getLogger(__name__)


class AdapterFactory:
    """Factory for creating configured adapter instances."""
    
    _bot_session_adapter: Optional[BotSessionServiceAdapter] = None
    _user_bot_session_adapter: Optional[UserBotConversationAdapter] = None
    _cart_order_adapter: Optional[CartOrderServiceAdapter] = None
    _delivery_adapter: Optional[DeliveryServiceAdapter] = None
    _payment_adapter: Optional[PaymentRevenueAdapter] = None
    _catalog_adapter: Optional[CatalogInventoryAdapter] = None
    _msme_adapter: Optional[MsmeEngineAdapter] = None
    _affiliate_adapter: Optional[AffiliateEngineAdapter] = None
    
    @classmethod
    def get_bot_session_adapter(cls) -> BotSessionServiceAdapter:
        """
        Get or create BotSessionServiceAdapter with real bot-session URL.
        
        Uses:
        - BOT_SESSION_URL environment variable
        - ICE_BOT_SESSION_TIMEOUT environment variable
        
        Returns:
            Configured BotSessionServiceAdapter instance
        """
        if cls._bot_session_adapter is None:
            logger.info(f"Creating BotSessionServiceAdapter with URL: {Config.BOT_SESSION_URL}")
            cls._bot_session_adapter = BotSessionServiceAdapter(
                base_url=Config.BOT_SESSION_URL,
                timeout=Config.ICE_BOT_SESSION_TIMEOUT
            )
        return cls._bot_session_adapter
    
    @classmethod
    def get_user_bot_session_adapter(cls) -> UserBotConversationAdapter:
        """
        Get or create UserBotConversationAdapter with real bot-session URL.
        
        Uses:
        - BOT_SESSION_URL environment variable
        - ICE_BOT_SESSION_TIMEOUT environment variable
        
        Returns:
            Configured UserBotConversationAdapter instance
        """
        if cls._user_bot_session_adapter is None:
            logger.info(f"Creating UserBotConversationAdapter with URL: {Config.BOT_SESSION_URL}")
            cls._user_bot_session_adapter = UserBotConversationAdapter(
                base_url=Config.BOT_SESSION_URL,
                timeout=Config.ICE_BOT_SESSION_TIMEOUT
            )
        return cls._user_bot_session_adapter
    
    @classmethod
    def get_cart_order_adapter(cls) -> CartOrderServiceAdapter:
        """
        Get or create CartOrderServiceAdapter with real Cart service URL.
        
        Uses:
        - CART_SERVICE_URL environment variable
        
        Returns:
            Configured CartOrderServiceAdapter instance
        """
        if cls._cart_order_adapter is None:
            logger.info(f"Creating CartOrderServiceAdapter with URL: {Config.CART_SERVICE_URL}")
            cls._cart_order_adapter = CartOrderServiceAdapter(
                base_url=Config.CART_SERVICE_URL,
                order_base_url=Config.ORDER_DELIVERY_URL,
                timeout=5.0
            )
        return cls._cart_order_adapter

    @classmethod
    def get_delivery_adapter(cls) -> DeliveryServiceAdapter:
        """
        Get or create DeliveryServiceAdapter with real Order-Delivery service URL.

        Uses:
        - ORDER_DELIVERY_URL environment variable

        Returns:
            Configured DeliveryServiceAdapter instance
        """
        if cls._delivery_adapter is None:
            logger.info(f"Creating DeliveryServiceAdapter with URL: {Config.ORDER_DELIVERY_URL}")
            cls._delivery_adapter = DeliveryServiceAdapter(
                base_url=Config.ORDER_DELIVERY_URL,
                timeout=5.0
            )
        return cls._delivery_adapter

    @classmethod
    def get_payment_adapter(cls) -> PaymentRevenueAdapter:
        """
        Get or create PaymentRevenueAdapter with real Payment-Revenue URL.

        Uses:
        - PAYMENT_REVENUE_URL environment variable

        Returns:
            Configured PaymentRevenueAdapter instance
        """
        if cls._payment_adapter is None:
            logger.info(f"Creating PaymentRevenueAdapter with URL: {Config.PAYMENT_REVENUE_URL}")
            cls._payment_adapter = PaymentRevenueAdapter(
                base_url=Config.PAYMENT_REVENUE_URL,
                timeout=5.0
            )
        return cls._payment_adapter
    
    @classmethod
    def get_catalog_adapter(cls) -> CatalogInventoryAdapter:
        """
        Get or create CatalogInventoryAdapter with real Catalog service URL.
        
        Uses:
        - CATALOG_INVENTORY_URL environment variable
        
        Returns:
            Configured CatalogInventoryAdapter instance
        """
        if cls._catalog_adapter is None:
            logger.info(f"Creating CatalogInventoryAdapter with URL: {Config.CATALOG_INVENTORY_URL}")
            cls._catalog_adapter = CatalogInventoryAdapter(
                base_url=Config.CATALOG_INVENTORY_URL,
                timeout=5.0
            )
        return cls._catalog_adapter
    
    @classmethod
    def get_msme_adapter(cls) -> MsmeEngineAdapter:
        """
        Get or create MsmeEngineAdapter with real MSME Engine URL.
        
        Uses:
        - MSME_ENGINE_URL environment variable
        
        Returns:
            Configured MsmeEngineAdapter instance
        """
        if cls._msme_adapter is None:
            logger.info(f"Creating MsmeEngineAdapter with URL: {Config.MSME_ENGINE_URL}")
            cls._msme_adapter = MsmeEngineAdapter(
                base_url=Config.MSME_ENGINE_URL
            )
        return cls._msme_adapter
    
    @classmethod
    def get_affiliate_adapter(cls) -> AffiliateEngineAdapter:
        """
        Get or create AffiliateEngineAdapter with real Affiliate Engine URL.
        
        Uses:
        - AFFILIATE_ENGINE_URL environment variable
        
        Returns:
            Configured AffiliateEngineAdapter instance
        """
        if cls._affiliate_adapter is None:
            logger.info(f"Creating AffiliateEngineAdapter with URL: {Config.AFFILIATE_ENGINE_URL}")
            cls._affiliate_adapter = AffiliateEngineAdapter(
                base_url=Config.AFFILIATE_ENGINE_URL
            )
        return cls._affiliate_adapter
    
    @classmethod
    async def cleanup(cls) -> None:
        """Close all adapter HTTP clients for graceful shutdown."""
        if cls._bot_session_adapter:
            logger.info("Closing BotSessionServiceAdapter")
            await cls._bot_session_adapter.close()
            cls._bot_session_adapter = None
        
        if cls._user_bot_session_adapter:
            logger.info("Closing UserBotConversationAdapter")
            await cls._user_bot_session_adapter.close()
            cls._user_bot_session_adapter = None
        
        if cls._cart_order_adapter:
            logger.info("Closing CartOrderServiceAdapter")
            await cls._cart_order_adapter.close()
            cls._cart_order_adapter = None

        if cls._delivery_adapter:
            logger.info("Closing DeliveryServiceAdapter")
            await cls._delivery_adapter.close()
            cls._delivery_adapter = None

        if cls._payment_adapter:
            logger.info("Closing PaymentRevenueAdapter")
            await cls._payment_adapter.close()
            cls._payment_adapter = None
        
        if cls._catalog_adapter:
            logger.info("Closing CatalogInventoryAdapter")
            await cls._catalog_adapter.close()
            cls._catalog_adapter = None
        
        if cls._msme_adapter:
            logger.info("Closing MsmeEngineAdapter")
            await cls._msme_adapter.cleanup()
            cls._msme_adapter = None
        
        if cls._affiliate_adapter:
            logger.info("Closing AffiliateEngineAdapter")
            await cls._affiliate_adapter.cleanup()
            cls._affiliate_adapter = None
