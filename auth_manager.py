"""
Authentication Manager for WebSocket Connections
Manages tokens and permissions for secure access
"""

import secrets
import hashlib
import json
import os
import logging
from typing import Optional, Set, Dict
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class AuthToken:
    """Authentication token for WebSocket connections"""
    token: str
    client_name: str
    permissions: Set[str]
    created_at: str
    expires_at: Optional[str] = None
    last_used: Optional[str] = None
    description: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['permissions'] = list(self.permissions)
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'AuthToken':
        """Create from dictionary"""
        data['permissions'] = set(data.get('permissions', []))
        return cls(**data)
    
    def is_expired(self) -> bool:
        """Check if token is expired"""
        if not self.expires_at:
            return False
        
        expires = datetime.fromisoformat(self.expires_at)
        return datetime.now() > expires


class AuthManager:
    """Manages authentication for WebSocket connections"""
    
    DEFAULT_PERMISSIONS = {
        "read": "Read tmux state and events",
        "write": "Send commands to tmux sessions",
        "admin": "Manage tokens and permissions",
        "snapshot": "Request state snapshots",
        "subscribe": "Subscribe to events"
    }
    
    def __init__(self, tokens_file: str = "websocket_tokens.json"):
        self.tokens_file = Path(tokens_file)
        self.tokens: Dict[str, AuthToken] = {}
        self.load_tokens()
        
        # Create default development token if no tokens exist
        if not self.tokens:
            self.create_development_token()
    
    def load_tokens(self):
        """Load tokens from file"""
        if self.tokens_file.exists():
            try:
                with open(self.tokens_file, 'r') as f:
                    data = json.load(f)
                    self.tokens = {
                        token: AuthToken.from_dict(token_data)
                        for token, token_data in data.items()
                    }
                logger.info(f"Loaded {len(self.tokens)} tokens from {self.tokens_file}")
            except Exception as e:
                logger.error(f"Error loading tokens: {e}")
                self.tokens = {}
        else:
            logger.info(f"No tokens file found at {self.tokens_file}")
    
    def save_tokens(self):
        """Save tokens to file"""
        try:
            data = {
                token: auth_token.to_dict()
                for token, auth_token in self.tokens.items()
            }
            
            with open(self.tokens_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Saved {len(self.tokens)} tokens to {self.tokens_file}")
        except Exception as e:
            logger.error(f"Error saving tokens: {e}")
    
    def generate_token(self, 
                      client_name: str,
                      permissions: Set[str],
                      expires_in_hours: Optional[int] = None,
                      description: Optional[str] = None) -> str:
        """Generate a new authentication token"""
        token_value = secrets.token_urlsafe(32)
        
        expires_at = None
        if expires_in_hours:
            expires_at = (datetime.now() + timedelta(hours=expires_in_hours)).isoformat()
        
        token = AuthToken(
            token=token_value,
            client_name=client_name,
            permissions=permissions,
            created_at=datetime.now().isoformat(),
            expires_at=expires_at,
            description=description
        )
        
        self.tokens[token_value] = token
        self.save_tokens()
        
        logger.info(f"Generated token for client '{client_name}' with permissions: {permissions}")
        return token_value
    
    def validate_token(self, token: str) -> Optional[AuthToken]:
        """Validate an authentication token"""
        if token in self.tokens:
            auth_token = self.tokens[token]
            
            # Check expiration
            if auth_token.is_expired():
                logger.warning(f"Token for '{auth_token.client_name}' has expired")
                del self.tokens[token]
                self.save_tokens()
                return None
            
            # Update last used timestamp
            auth_token.last_used = datetime.now().isoformat()
            self.save_tokens()
            
            return auth_token
        
        logger.warning(f"Invalid token attempted: {token[:8]}...")
        return None
    
    def has_permission(self, token: str, permission: str) -> bool:
        """Check if a token has a specific permission"""
        auth_token = self.validate_token(token)
        if auth_token:
            has_perm = permission in auth_token.permissions or "admin" in auth_token.permissions
            if not has_perm:
                logger.warning(f"Token for '{auth_token.client_name}' lacks permission: {permission}")
            return has_perm
        return False
    
    def revoke_token(self, token: str) -> bool:
        """Revoke a token"""
        if token in self.tokens:
            client_name = self.tokens[token].client_name
            del self.tokens[token]
            self.save_tokens()
            logger.info(f"Revoked token for client '{client_name}'")
            return True
        return False
    
    def list_tokens(self) -> Dict[str, Dict]:
        """List all tokens (without exposing the actual token values)"""
        return {
            token[:8] + "...": {
                "client_name": auth_token.client_name,
                "permissions": list(auth_token.permissions),
                "created_at": auth_token.created_at,
                "expires_at": auth_token.expires_at,
                "last_used": auth_token.last_used,
                "description": auth_token.description
            }
            for token, auth_token in self.tokens.items()
        }
    
    def create_development_token(self):
        """Create a default development token"""
        token = self.generate_token(
            client_name="development",
            permissions={"read", "write", "snapshot", "subscribe"},
            description="Default development token - DELETE IN PRODUCTION"
        )
        logger.warning(f"Created development token: {token}")
        logger.warning("WARNING: This token should be deleted in production!")
        return token
    
    def cleanup_expired_tokens(self):
        """Remove all expired tokens"""
        expired = []
        for token, auth_token in self.tokens.items():
            if auth_token.is_expired():
                expired.append(token)
        
        for token in expired:
            del self.tokens[token]
        
        if expired:
            self.save_tokens()
            logger.info(f"Cleaned up {len(expired)} expired tokens")
    
    def hash_token(self, token: str) -> str:
        """Hash a token for secure storage/comparison"""
        return hashlib.sha256(token.encode()).hexdigest()


class TokenGenerator:
    """Utility class for generating tokens from command line"""
    
    def __init__(self, auth_manager: AuthManager):
        self.auth_manager = auth_manager
    
    def interactive_generate(self):
        """Interactive token generation"""
        print("\n=== WebSocket Token Generator ===\n")
        
        client_name = input("Client name: ").strip()
        if not client_name:
            print("Error: Client name is required")
            return
        
        print("\nAvailable permissions:")
        for perm, desc in AuthManager.DEFAULT_PERMISSIONS.items():
            print(f"  - {perm}: {desc}")
        
        perms_input = input("\nPermissions (comma-separated, or 'all' for all): ").strip()
        
        if perms_input.lower() == 'all':
            permissions = set(AuthManager.DEFAULT_PERMISSIONS.keys())
        else:
            permissions = {p.strip() for p in perms_input.split(',') if p.strip()}
        
        if not permissions:
            print("Error: At least one permission is required")
            return
        
        expires_input = input("Expires in hours (leave empty for no expiration): ").strip()
        expires_in_hours = None
        if expires_input:
            try:
                expires_in_hours = int(expires_input)
            except ValueError:
                print("Error: Invalid expiration hours")
                return
        
        description = input("Description (optional): ").strip() or None
        
        # Generate token
        token = self.auth_manager.generate_token(
            client_name=client_name,
            permissions=permissions,
            expires_in_hours=expires_in_hours,
            description=description
        )
        
        print(f"\n{'='*60}")
        print(f"Token generated successfully!")
        print(f"{'='*60}")
        print(f"Client: {client_name}")
        print(f"Permissions: {', '.join(permissions)}")
        if expires_in_hours:
            print(f"Expires in: {expires_in_hours} hours")
        print(f"\nToken:\n{token}")
        print(f"{'='*60}")
        print("\nSave this token securely - it cannot be retrieved later!")


def main():
    """Main entry point for token management"""
    import sys
    
    auth_manager = AuthManager()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "generate":
            generator = TokenGenerator(auth_manager)
            generator.interactive_generate()
        
        elif command == "list":
            tokens = auth_manager.list_tokens()
            if tokens:
                print("\n=== Active Tokens ===\n")
                for token_preview, info in tokens.items():
                    print(f"Token: {token_preview}")
                    print(f"  Client: {info['client_name']}")
                    print(f"  Permissions: {', '.join(info['permissions'])}")
                    print(f"  Created: {info['created_at']}")
                    if info.get('expires_at'):
                        print(f"  Expires: {info['expires_at']}")
                    if info.get('description'):
                        print(f"  Description: {info['description']}")
                    print()
            else:
                print("No tokens found")
        
        elif command == "cleanup":
            auth_manager.cleanup_expired_tokens()
            print("Expired tokens cleaned up")
        
        else:
            print(f"Unknown command: {command}")
            print("Usage: python auth_manager.py [generate|list|cleanup]")
    else:
        print("WebSocket Authentication Manager")
        print("Usage: python auth_manager.py [generate|list|cleanup]")
        print("  generate - Generate a new token")
        print("  list     - List all tokens")
        print("  cleanup  - Remove expired tokens")


if __name__ == "__main__":
    main()