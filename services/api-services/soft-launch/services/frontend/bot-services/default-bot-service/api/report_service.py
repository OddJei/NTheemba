"""Report service API client."""

import logging
import requests
from typing import Dict, Any, List, Optional
from config.environment import config

logger = logging.getLogger(__name__)

class ReportServiceClient:
    """Client for report service"""
    
    def __init__(self):
        self.base_url = config.get_service_url("REPORT_SERVICE")
        self.timeout = config.get_service_timeout("REPORT_SERVICE")
        self.api_key = config.get("API_KEY_VALUE")
    
    def _make_request(self, method: str, endpoint: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make HTTP request to report service"""
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
            logger.error(f"Report service request failed: {e}")
            return {"error": f"Report service error: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error in report service: {e}")
            return {"error": f"Unexpected error: {str(e)}"}
    
    def generate_report(self, report_type: str, filters: Dict[str, Any], format: str = "pdf") -> Dict[str, Any]:
        """Generate report"""
        try:
            data = {
                "report_type": report_type,
                "filters": filters,
                "format": format
            }
            result = self._make_request("POST", "/reports/generate", data)
            
            if "error" not in result:
                logger.info(f"Report generated: {report_type}")
            else:
                logger.warning(f"Failed to generate report: {report_type}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return {"error": f"Report generation error: {str(e)}"}
    
    def get_report_status(self, report_id: str) -> Dict[str, Any]:
        """Get report generation status"""
        try:
            result = self._make_request("GET", f"/reports/{report_id}/status")
            
            if "error" not in result:
                logger.info(f"Report status retrieved: {report_id}")
            else:
                logger.warning(f"Failed to get report status: {report_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting report status: {e}")
            return {"error": f"Report status error: {str(e)}"}
    
    def download_report(self, report_id: str) -> Dict[str, Any]:
        """Download generated report"""
        try:
            result = self._make_request("GET", f"/reports/{report_id}/download")
            
            if "error" not in result:
                logger.info(f"Report downloaded: {report_id}")
            else:
                logger.warning(f"Failed to download report: {report_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error downloading report: {e}")
            return {"error": f"Report download error: {str(e)}"}
    
    def get_available_reports(self) -> Dict[str, Any]:
        """Get available report types"""
        try:
            result = self._make_request("GET", "/reports/types")
            
            if "error" not in result:
                logger.info("Available reports retrieved")
            else:
                logger.warning("Failed to get available reports")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting available reports: {e}")
            return {"error": f"Available reports error: {str(e)}"}



