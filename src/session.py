"""
Module de gestion de session Voilà.ca

Gère les cookies et l'authentification avec:
- Persistance des cookies de session (conversion session -> persistent)
- Validation de session avec cache
- Refresh automatique si possible
- Health check avant opérations
"""

import json
import time
import os
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import requests

from .exceptions import VoilaSessionExpired, VoilaAuthRequired


@dataclass
class SessionStatus:
    """État de la session"""
    authenticated: bool
    email: Optional[str] = None
    customer_name: Optional[str] = None
    checked_at: Optional[str] = None
    expires_soon: bool = False  # True si cookies expirent dans < 24h
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'SessionStatus':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class SessionManager:
    """Gestion des sessions Voilà.ca avec persistance améliorée"""
    
    BASE_URL = "https://voila.ca"
    SESSION_VERSION = 3
    
    # Cookies critiques pour l'authentification
    CRITICAL_COOKIES = ['global_sid', 'userId', 'VISITORID', 'userEmail']
    
    # Durée par défaut pour les session cookies (7 jours)
    DEFAULT_SESSION_EXPIRY_DAYS = 7
    
    # Cache de validation (5 minutes)
    VALIDATION_CACHE_SECONDS = 300
    
    def __init__(self, session_file: Optional[Path] = None):
        """
        Initialise le gestionnaire de session.
        
        Args:
            session_file: Chemin vers le fichier de session
        """
        self.session_file = Path(session_file).expanduser() if session_file else Path("~/.voila-session.json").expanduser()
        self._data: Dict[str, Any] = self._default_data()
        self._load()
    
    def _default_data(self) -> Dict[str, Any]:
        """Données par défaut pour une nouvelle session"""
        return {
            'version': self.SESSION_VERSION,
            'cookies': [],
            'product_cache': {},
            'status': None,
            'last_validation': None,
            'last_activity': None,
            'created_at': datetime.now().isoformat()
        }
    
    def _load(self) -> bool:
        """Charge la session depuis le fichier"""
        if not self.session_file.exists():
            return False
        
        try:
            with open(self.session_file) as f:
                data = json.load(f)
            
            # Migration depuis anciens formats
            if isinstance(data, list):
                # Format très ancien (liste de cookies)
                self._data = self._default_data()
                self._data['cookies'] = data
            elif data.get('version', 1) < 3:
                # Migration v1/v2 -> v3
                self._data = self._default_data()
                self._data['cookies'] = data.get('cookies', [])
                self._data['product_cache'] = data.get('product_cache', {})
            else:
                self._data = data
            
            return True
        except Exception:
            return False
    
    def save(self) -> None:
        """Sauvegarde la session avec cookies persistants"""
        # Convertir les session cookies en persistent avant sauvegarde
        self._make_cookies_persistent()
        
        self._data['last_activity'] = datetime.now().isoformat()
        
        self.session_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.session_file, 'w') as f:
            json.dump(self._data, f, indent=2)
        self.session_file.chmod(0o600)
    
    def _make_cookies_persistent(self) -> None:
        """Convertit les session cookies en cookies persistants"""
        now = time.time()
        default_expiry = now + (self.DEFAULT_SESSION_EXPIRY_DAYS * 24 * 60 * 60)
        
        for cookie in self._data.get('cookies', []):
            expires = cookie.get('expires', 0)
            # Si pas d'expiration ou expiration = 0 (session cookie)
            if not expires or expires == 0 or expires == -1:
                cookie['expires'] = default_expiry
    
    @property
    def cookies(self) -> List[Dict]:
        """Retourne les cookies (format Playwright)"""
        return self._data.get('cookies', [])
    
    @cookies.setter
    def cookies(self, value: List[Dict]) -> None:
        """Définit les cookies et invalide le cache de validation"""
        self._data['cookies'] = value
        self._data['status'] = None
        self._data['last_validation'] = None
    
    @property
    def product_cache(self) -> Dict[str, str]:
        """Cache productId -> productName"""
        return self._data.get('product_cache', {})
    
    def cache_product(self, product_id: str, product_name: str) -> None:
        """Ajoute un produit au cache"""
        if 'product_cache' not in self._data:
            self._data['product_cache'] = {}
        self._data['product_cache'][product_id] = product_name
    
    def get_cookies_dict(self) -> Dict[str, str]:
        """Retourne les cookies en format simple {name: value}"""
        return {c['name']: c['value'] for c in self.cookies}
    
    def get_cookies_for_requests(self) -> Dict[str, str]:
        """Retourne les cookies pour requests library"""
        return self.get_cookies_dict()
    
    def import_cookies(self, source: Path) -> Tuple[int, str]:
        """
        Importe des cookies depuis un fichier.
        
        Formats supportés:
        - Playwright: [{name, value, domain, ...}, ...]
        - Firefox/EditThisCookie: [{Name raw, Content raw, ...}, ...]
        - Simple: {name: value, ...}
        
        Returns:
            Tuple (nombre de cookies importés, message)
        """
        with open(source) as f:
            raw_data = json.load(f)
        
        cookies = []
        
        # Detect format
        if isinstance(raw_data, list):
            for c in raw_data:
                if isinstance(c, dict):
                    # Firefox export format
                    if 'Name raw' in c:
                        cookies.append(self._convert_firefox_cookie(c))
                    # Playwright/standard format
                    elif 'name' in c:
                        cookies.append(self._normalize_cookie(c))
        elif isinstance(raw_data, dict):
            if 'cookies' in raw_data:
                for c in raw_data['cookies']:
                    if 'Name raw' in c:
                        cookies.append(self._convert_firefox_cookie(c))
                    else:
                        cookies.append(self._normalize_cookie(c))
            else:
                # Simple {name: value} format
                for name, value in raw_data.items():
                    cookies.append({
                        'name': name,
                        'value': str(value),
                        'domain': '.voila.ca',
                        'path': '/',
                        'secure': True,
                        'httpOnly': False
                    })
        
        # Merge avec cookies existants (nouveaux remplacent anciens)
        existing = {c['name']: c for c in self._data.get('cookies', [])}
        for c in cookies:
            existing[c['name']] = c
        
        self._data['cookies'] = list(existing.values())
        self._data['status'] = None
        self._data['last_validation'] = None
        self.save()
        
        return len(cookies), f"{len(cookies)} cookies importés"
    
    def _convert_firefox_cookie(self, c: dict) -> dict:
        """Convertit un cookie Firefox en format standard"""
        return {
            'name': c.get('Name raw', ''),
            'value': c.get('Content raw', ''),
            'domain': '.voila.ca',
            'path': c.get('Path raw', '/'),
            'secure': c.get('Send for raw') == 'true',
            'httpOnly': c.get('HTTP only raw') == 'true',
            'sameSite': 'None' if c.get('SameSite raw') == 'no_restriction' else 'Lax'
        }
    
    def _normalize_cookie(self, c: dict) -> dict:
        """Normalise un cookie au format standard"""
        return {
            'name': c.get('name', ''),
            'value': c.get('value', ''),
            'domain': c.get('domain', '.voila.ca'),
            'path': c.get('path', '/'),
            'secure': c.get('secure', True),
            'httpOnly': c.get('httpOnly', False),
            'sameSite': c.get('sameSite', 'Lax'),
            'expires': c.get('expires', 0)
        }
    
    def validate_session(self, force: bool = False) -> SessionStatus:
        """
        Valide la session et retourne son état.
        
        Args:
            force: Force la revalidation même si cache valide
            
        Returns:
            SessionStatus avec état de la session
        """
        # Check cache
        if not force and self._data.get('status') and self._data.get('last_validation'):
            try:
                last = datetime.fromisoformat(self._data['last_validation'])
                if (datetime.now() - last).total_seconds() < self.VALIDATION_CACHE_SECONDS:
                    return SessionStatus.from_dict(self._data['status'])
            except:
                pass
        
        status = SessionStatus(authenticated=False)
        
        try:
            # Utiliser Playwright pour vérifier l'auth via __INITIAL_STATE__
            from playwright.sync_api import sync_playwright
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                context.add_cookies(self.cookies)
                
                page = context.new_page()
                page.goto(f"{self.BASE_URL}", wait_until='domcontentloaded', timeout=20000)
                page.wait_for_timeout(2000)
                
                # Extraire les données du customer depuis __INITIAL_STATE__
                customer = page.evaluate('''() => {
                    const s = window.__INITIAL_STATE__;
                    return s?.data?.customer?.details?.data || null;
                }''')
                
                browser.close()
            
            if customer and customer.get('email'):
                status = SessionStatus(
                    authenticated=True,
                    email=customer.get('email'),
                    customer_name=customer.get('fullName') or customer.get('moniker')
                )
            
            # Vérifier expiration des cookies
            status.expires_soon = self._check_cookies_expiring_soon()
            
        except Exception as e:
            status = SessionStatus(authenticated=False)
        
        # Mettre en cache
        status.checked_at = datetime.now().isoformat()
        self._data['status'] = status.to_dict()
        self._data['last_validation'] = datetime.now().isoformat()
        self.save()
        
        return status
    
    def _check_cookies_expiring_soon(self, hours: int = 24) -> bool:
        """Vérifie si des cookies critiques expirent bientôt"""
        threshold = time.time() + (hours * 60 * 60)
        
        for cookie in self.cookies:
            if cookie.get('name') in self.CRITICAL_COOKIES:
                expires = cookie.get('expires', 0)
                if expires and 0 < expires < threshold:
                    return True
        return False
    
    def is_authenticated(self) -> bool:
        """Vérifie si la session est authentifiée"""
        status = self.validate_session()
        return status.authenticated
    
    def refresh_session(self) -> bool:
        """
        Tente de rafraîchir la session en accédant au site.
        
        Cela peut renouveler les cookies de session.
        
        Returns:
            True si session rafraîchie avec succès
        """
        try:
            from playwright.sync_api import sync_playwright
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                context.add_cookies(self.cookies)
                
                page = context.new_page()
                page.goto(f"{self.BASE_URL}", wait_until='domcontentloaded', timeout=30000)
                page.wait_for_timeout(3000)
                
                # Récupérer les cookies mis à jour
                new_cookies = context.cookies()
                
                browser.close()
            
            # Merger les nouveaux cookies
            existing = {c['name']: c for c in self.cookies}
            for c in new_cookies:
                if '.voila.ca' in c.get('domain', ''):
                    existing[c['name']] = c
            
            self._data['cookies'] = list(existing.values())
            self._data['status'] = None  # Invalider le cache
            self.save()
            
            return True
            
        except Exception:
            return False
    
    def get_session_info(self) -> Dict[str, Any]:
        """Retourne un résumé de l'état de la session"""
        status = self.validate_session()
        
        # Compter les cookies par type
        total = len(self.cookies)
        critical_count = sum(1 for c in self.cookies if c.get('name') in self.CRITICAL_COOKIES)
        
        # Trouver la plus proche expiration des cookies CRITIQUES
        now = time.time()
        critical_expiry = None
        for c in self.cookies:
            if c.get('name') in self.CRITICAL_COOKIES:
                exp = c.get('expires', 0)
                if exp and exp > now:
                    if critical_expiry is None or exp < critical_expiry:
                        critical_expiry = exp
        
        # Calculer les jours restants
        days_remaining = None
        if critical_expiry:
            days_remaining = int((critical_expiry - now) / (24 * 60 * 60))
        
        return {
            'authenticated': status.authenticated,
            'email': status.email,
            'customer_name': status.customer_name,
            'expires_soon': status.expires_soon,
            'total_cookies': total,
            'critical_cookies': critical_count,
            'critical_expiry': datetime.fromtimestamp(critical_expiry).isoformat() if critical_expiry else None,
            'days_remaining': days_remaining,
            'last_activity': self._data.get('last_activity'),
            'session_file': str(self.session_file)
        }
    
    def clear(self) -> None:
        """Efface la session"""
        self._data = self._default_data()
        self.save()


def create_session_manager(session_file: Optional[str] = None) -> SessionManager:
    """Factory pour créer un SessionManager"""
    return SessionManager(
        session_file=Path(session_file) if session_file else None
    )
