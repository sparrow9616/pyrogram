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

import asyncio
import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Optional, Callable, Dict, Any, List
from urllib.parse import urlparse, parse_qs
import hashlib
import hmac

import pyrogram
from pyrogram import raw, types, utils

log = logging.getLogger(__name__)


class WebhookHandler(BaseHTTPRequestHandler):
    """HTTP request handler for webhook endpoint."""
    
    def __init__(self, webhook_server: "WebhookServer", *args, **kwargs):
        self.webhook_server = webhook_server
        super().__init__(*args, **kwargs)
    
    def do_POST(self):
        """Handle POST requests to webhook endpoint."""
        try:
            # Parse the URL path
            parsed_path = urlparse(self.path)
            
            # Check if this is a webhook endpoint
            if not parsed_path.path.startswith('/webhook/'):
                self.send_response(404)
                self.end_headers()
                return
            
            # Extract token from path
            path_parts = parsed_path.path.split('/')
            if len(path_parts) < 3:
                self.send_response(404)
                self.end_headers()
                return
            
            token = path_parts[2]
            
            # Verify token
            if not self.webhook_server.verify_token(token):
                self.send_response(403)
                self.end_headers()
                return
            
            # Read and parse JSON body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            
            # Verify secret if configured
            if self.webhook_server.secret_token:
                signature = self.headers.get('X-Telegram-Bot-Api-Secret-Token')
                if not self._verify_signature(body, signature):
                    self.send_response(403)
                    self.end_headers()
                    return
            
            try:
                update_data = json.loads(body.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                self.send_response(400)
                self.end_headers()
                return
            
            # Process the update
            asyncio.run_coroutine_threadsafe(
                self.webhook_server.process_update(update_data),
                self.webhook_server.loop
            )
            
            # Send 200 OK response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"ok": true}')
            
        except Exception as e:
            log.error(f"Error processing webhook request: {e}")
            self.send_response(500)
            self.end_headers()
    
    def _verify_signature(self, body: bytes, signature: Optional[str]) -> bool:
        """Verify webhook signature using secret token."""
        if not signature or not self.webhook_server.secret_token:
            return False
        
        expected_signature = hmac.new(
            self.webhook_server.secret_token.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    def log_message(self, format, *args):
        """Override to suppress default HTTP logging."""
        pass


class WebhookServer:
    """Webhook server for receiving Telegram Bot API updates."""
    
    def __init__(self, client: "pyrogram.Client"):
        self.client = client
        self.loop = client.loop
        self.server: Optional[HTTPServer] = None
        self.server_thread: Optional[Thread] = None
        self.webhook_url: Optional[str] = None
        self.secret_token: Optional[str] = None
        self.allowed_updates: Optional[List[str]] = None
        self.is_running = False
    
    def start_server(self, host: str = "0.0.0.0", port: int = 8080):
        """Start the webhook HTTP server."""
        if self.is_running:
            log.warning("Webhook server is already running")
            return
        
        try:
            # Create handler class with webhook server reference
            def handler(*args, **kwargs):
                return WebhookHandler(self, *args, **kwargs)
            
            self.server = HTTPServer((host, port), handler)
            self.server_thread = Thread(target=self.server.serve_forever, daemon=True)
            self.server_thread.start()
            self.is_running = True
            
            log.info(f"Webhook server started on {host}:{port}")
            
        except Exception as e:
            log.error(f"Failed to start webhook server: {e}")
            raise
    
    def stop_server(self):
        """Stop the webhook HTTP server."""
        if not self.is_running:
            return
        
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        
        if self.server_thread:
            self.server_thread.join()
        
        self.is_running = False
        log.info("Webhook server stopped")
    
    def verify_token(self, token: str) -> bool:
        """Verify if the token matches the bot token."""
        if not self.client.bot_token:
            return False
        
        return token == self.client.bot_token.split(':')[0]
    
    async def process_update(self, update_data: Dict[str, Any]):
        """Process incoming webhook update."""
        try:
            # Convert Bot API update to MTProto-style update
            converted_update = await self._convert_bot_api_update(update_data)
            
            if converted_update:
                # Process through normal Pyrogram update handling
                await self.client.handle_updates(converted_update)
            
        except Exception as e:
            log.error(f"Error processing webhook update: {e}")
    
    async def _convert_bot_api_update(self, bot_api_update: Dict[str, Any]) -> Optional[Any]:
        """Convert Bot API update format to MTProto update format."""
        # This is a complex conversion that would need to handle all Bot API update types
        # For now, implementing basic message updates
        
        if "message" in bot_api_update:
            return await self._convert_message_update(bot_api_update["message"])
        elif "edited_message" in bot_api_update:
            return await self._convert_edited_message_update(bot_api_update["edited_message"])
        elif "callback_query" in bot_api_update:
            return await self._convert_callback_query_update(bot_api_update["callback_query"])
        
        log.debug(f"Unhandled Bot API update type: {list(bot_api_update.keys())}")
        return None
    
    async def _convert_message_update(self, message: Dict[str, Any]) -> raw.types.UpdateNewMessage:
        """Convert Bot API message to MTProto UpdateNewMessage."""
        # This is a simplified conversion - in reality, this would need extensive mapping
        # between Bot API and MTProto message structures
        
        # For demonstration purposes, creating a basic structure
        # In practice, this would require comprehensive field mapping
        
        peer = await self._get_peer_from_bot_api_chat(message.get("chat", {}))
        user = await self._get_user_from_bot_api_user(message.get("from", {}))
        
        mtproto_message = raw.types.Message(
            id=message.get("message_id", 0),
            peer_id=peer,
            from_id=raw.types.PeerUser(user_id=user.id) if user else None,
            date=message.get("date", 0),
            message=message.get("text", ""),
            # Additional fields would need to be mapped here
        )
        
        return raw.types.UpdateNewMessage(
            message=mtproto_message,
            pts=0,  # This would need proper handling
            pts_count=1
        )
    
    async def _convert_edited_message_update(self, message: Dict[str, Any]) -> raw.types.UpdateEditMessage:
        """Convert Bot API edited message to MTProto UpdateEditMessage."""
        # Similar to _convert_message_update but for edited messages
        # Implementation would be similar but return UpdateEditMessage
        pass
    
    async def _convert_callback_query_update(self, callback_query: Dict[str, Any]) -> raw.types.UpdateBotCallbackQuery:
        """Convert Bot API callback query to MTProto UpdateBotCallbackQuery."""
        # Convert callback query from Bot API to MTProto format
        pass
    
    async def _get_peer_from_bot_api_chat(self, chat: Dict[str, Any]) -> raw.base.Peer:
        """Convert Bot API chat to MTProto peer."""
        chat_id = chat.get("id", 0)
        chat_type = chat.get("type", "")
        
        if chat_type == "private":
            return raw.types.PeerUser(user_id=chat_id)
        elif chat_type in ("group", "supergroup"):
            if chat_id < 0:
                return raw.types.PeerChannel(channel_id=utils.get_channel_id(chat_id))
            return raw.types.PeerChat(chat_id=chat_id)
        elif chat_type == "channel":
            return raw.types.PeerChannel(channel_id=utils.get_channel_id(chat_id))
        
        return raw.types.PeerUser(user_id=chat_id)
    
    async def _get_user_from_bot_api_user(self, user: Dict[str, Any]) -> Optional[raw.types.User]:
        """Convert Bot API user to MTProto user."""
        if not user:
            return None
        
        return raw.types.User(
            id=user.get("id", 0),
            is_self=False,
            is_contact=False,
            is_mutual_contact=False,
            is_deleted=False,
            is_bot=user.get("is_bot", False),
            is_verified=False,
            is_restricted=False,
            is_scam=False,
            is_fake=False,
            is_premium=user.get("is_premium", False),
            first_name=user.get("first_name"),
            last_name=user.get("last_name"),
            username=user.get("username"),
            # Additional fields would need proper mapping
        )