"""Utility for getting the cloudflared tunnel URL at runtime."""

import asyncio
import re
from typing import Optional

import aiohttp
from loguru import logger


class TunnelURLProvider:
    """Provider for getting tunnel URLs from cloudflared service."""

    _tunnel_checked: bool = False
    _cached_urls: Optional[tuple[str, str]] = None

    @classmethod
    async def get_tunnel_urls(cls) -> tuple[str, str]:
        """
        Get the tunnel URLs for external access.

        Returns:
            tuple[str, str]: (https_url, wss_url) - Both URLs include full protocol

        Raises:
            ValueError: If no tunnel URL can be determined
        """
        if cls._tunnel_checked:
            if cls._cached_urls:
                return cls._cached_urls
            raise ValueError("No tunnel URL available")

        # In local dev environment without explicit tunnel enabled, fail fast immediately
        import os
        enable_tunnel = os.getenv("ENABLE_TUNNEL", "false").lower() == "true"
        if not enable_tunnel:
            cls._tunnel_checked = True
            cls._cached_urls = None
            raise ValueError("Tunnel resolution skipped: ENABLE_TUNNEL is not true")

        try:
            urls = await cls._get_cloudflared_urls()
            cls._tunnel_checked = True
            if urls:
                cls._cached_urls = urls
                return urls
        except Exception as e:
            cls._tunnel_checked = True
            logger.warning(f"Failed to get tunnel URL from cloudflared: {e}")

        cls._tunnel_checked = True
        raise ValueError(
            "No tunnel URL available. Please set BACKEND_API_ENDPOINT environment "
            "variable or ensure cloudflared service is running."
        )

    @classmethod
    async def _get_cloudflared_urls(cls) -> Optional[tuple[str, str]]:
        """
        Query cloudflared metrics endpoint to get the tunnel URLs.

        Returns:
            Optional[tuple[str, str]]: (https_url, wss_url) with full protocols, or None if not found
        """
        try:
            metrics_url = "http://cloudflared:2000/metrics"

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    metrics_url, timeout=aiohttp.ClientTimeout(total=0.5, connect=0.3)
                ) as response:
                    if response.status != 200:
                        logger.warning(
                            f"Cloudflared metrics returned status {response.status}"
                        )
                        return None

                    text = await response.text()

                    # Look for the tunnel URL in metrics
                    # Cloudflared exposes this in the userHostname metric
                    match = re.search(r'userHostname="([^"]+)"', text)
                    if match:
                        hostname = match.group(1)
                        # Remove https:// or wss:// if present
                        hostname = hostname.replace("https://", "").replace(
                            "wss://", ""
                        )
                        return "https://" + hostname, "wss://" + hostname

                    # Alternative: Look for trycloudflare.com domain
                    match = re.search(r"([a-z0-9-]+\.trycloudflare\.com)", text)
                    if match:
                        hostname = match.group(1)
                        hostname = hostname.replace("https://", "").replace(
                            "wss://", ""
                        )
                        return f"https://{hostname}", f"wss://{hostname}"

                    logger.warning("Could not find tunnel URL in cloudflared metrics")
                    return None

        except asyncio.TimeoutError:
            logger.warning("Timeout connecting to cloudflared metrics endpoint")
            return None
        except aiohttp.ClientError as e:
            logger.warning(f"Error connecting to cloudflared: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting cloudflared URL: {e}")
            return None
