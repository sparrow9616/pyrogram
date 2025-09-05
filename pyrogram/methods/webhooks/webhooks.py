#  Pyrogram - Telegram MTProto API Client Library for Python
#  Copyright (C) 2017-present Dan <https://github.com/delivrance>
#
#  This file is part of Pyrogram.
#
#  Pyrogram is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Lesser General Public License as published
#  by the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Pyrogram is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with Pyrogram.  If not, see <http://www.gnu.org/licenses/>.

import logging
from typing import Optional, List, Union
import httpx

import pyrogram
from pyrogram import raw, types

log = logging.getLogger(__name__)


class WebhookMethods:
    """Methods for managing Telegram Bot API webhooks."""
    
    async def set_webhook(
        self: "pyrogram.Client",
        url: str,
        certificate: Optional[Union[str, bytes]] = None,
        ip_address: Optional[str] = None,
        max_connections: Optional[int] = None,
        allowed_updates: Optional[List[str]] = None,
        drop_pending_updates: Optional[bool] = None,
        secret_token: Optional[str] = None,
        start_local_server: bool = False,
        server_host: str = "0.0.0.0",
        server_port: int = 8080
    ) -> bool:
        """Set a webhook for receiving updates.
        
        This method allows you to specify a URL where Telegram will send updates
        in Bot API format. This is an alternative to the default MTProto real-time
        updates that Pyrogram normally uses.
        
        Parameters:
            url (``str``):
                HTTPS URL to send updates to. Use an empty string to remove webhook integration.
                
            certificate (``str`` | ``bytes``, *optional*):
                Upload your public key certificate so that the root certificate 
                in use can be checked.
                
            ip_address (``str``, *optional*):
                The fixed IP address which will be used to send webhook requests 
                instead of the IP address resolved through DNS.
                
            max_connections (``int``, *optional*):
                The maximum allowed number of simultaneous HTTPS connections to 
                the webhook for update delivery, 1-100. Defaults to 40.
                
            allowed_updates (List of ``str``, *optional*):
                A list of the update types you want your bot to receive.
                
            drop_pending_updates (``bool``, *optional*):
                Pass True to drop all pending updates.
                
            secret_token (``str``, *optional*):
                A secret token to be sent in a header "X-Telegram-Bot-Api-Secret-Token" 
                in every webhook request.
                
            start_local_server (``bool``, *optional*):
                Whether to start a local HTTP server to handle webhook requests.
                Defaults to False.
                
            server_host (``str``, *optional*):
                Host address for the local webhook server. Defaults to "0.0.0.0".
                
            server_port (``int``, *optional*):
                Port for the local webhook server. Defaults to 8080.
        
        Returns:
            ``bool``: True on success.
            
        Example:
            .. code-block:: python
            
                # Set webhook with external URL
                await app.set_webhook("https://example.com/webhook/bot123456")
                
                # Set webhook with local server
                await app.set_webhook(
                    "https://example.com/webhook/bot123456", 
                    start_local_server=True,
                    server_port=8443
                )
                
                # Remove webhook
                await app.set_webhook("")
        """
        if not self.bot_token:
            raise ValueError("Webhooks are only supported for bot accounts. Use bot_token when creating the client.")
        
        # Prepare the request data
        data = {"url": url}
        
        if certificate is not None:
            data["certificate"] = certificate
            
        if ip_address is not None:
            data["ip_address"] = ip_address
            
        if max_connections is not None:
            data["max_connections"] = max_connections
            
        if allowed_updates is not None:
            data["allowed_updates"] = allowed_updates
            
        if drop_pending_updates is not None:
            data["drop_pending_updates"] = drop_pending_updates
            
        if secret_token is not None:
            data["secret_token"] = secret_token
        
        # Make API call to Telegram Bot API
        response = await self._make_bot_api_request("setWebhook", data)
        
        if response.get("ok"):
            # Store webhook configuration
            if not hasattr(self, 'webhook_server'):
                from pyrogram.webhook import WebhookServer
                self.webhook_server = WebhookServer(self)
            
            self.webhook_server.webhook_url = url
            self.webhook_server.secret_token = secret_token
            self.webhook_server.allowed_updates = allowed_updates
            
            # Start local server if requested
            if start_local_server and url:
                self.webhook_server.start_server(server_host, server_port)
            elif not url:
                # Stop server if webhook is being removed
                if hasattr(self, 'webhook_server'):
                    self.webhook_server.stop_server()
            
            log.info(f"Webhook {'set' if url else 'removed'} successfully")
            return True
        else:
            log.error(f"Failed to set webhook: {response}")
            return False
    
    async def delete_webhook(
        self: "pyrogram.Client",
        drop_pending_updates: Optional[bool] = None
    ) -> bool:
        """Remove webhook integration.
        
        Parameters:
            drop_pending_updates (``bool``, *optional*):
                Pass True to drop all pending updates.
        
        Returns:
            ``bool``: True on success.
            
        Example:
            .. code-block:: python
            
                await app.delete_webhook()
        """
        return await self.set_webhook("", drop_pending_updates=drop_pending_updates)
    
    async def get_webhook_info(self: "pyrogram.Client") -> "types.WebhookInfo":
        """Get current webhook status.
        
        Returns:
            :obj:`~pyrogram.types.WebhookInfo`: Current webhook information.
            
        Example:
            .. code-block:: python
            
                webhook_info = await app.get_webhook_info()
                print(f"Webhook URL: {webhook_info.url}")
        """
        if not self.bot_token:
            raise ValueError("Webhooks are only supported for bot accounts. Use bot_token when creating the client.")
        
        response = await self._make_bot_api_request("getWebhookInfo", {})
        
        if response.get("ok"):
            result = response["result"]
            return types.WebhookInfo(
                url=result.get("url", ""),
                has_custom_certificate=result.get("has_custom_certificate", False),
                pending_update_count=result.get("pending_update_count", 0),
                ip_address=result.get("ip_address"),
                last_error_date=result.get("last_error_date"),
                last_error_message=result.get("last_error_message"),
                last_synchronization_error_date=result.get("last_synchronization_error_date"),
                max_connections=result.get("max_connections"),
                allowed_updates=result.get("allowed_updates")
            )
        else:
            raise Exception(f"Failed to get webhook info: {response}")
    
    async def _make_bot_api_request(self: "pyrogram.Client", method: str, data: dict) -> dict:
        """Make a request to Telegram Bot API."""
        if not self.bot_token:
            raise ValueError("Bot token is required for Bot API requests")
        
        url = f"https://api.telegram.org/bot{self.bot_token}/{method}"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data)
            return response.json()