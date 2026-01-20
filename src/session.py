"""
Module de gestion de session Voilà.ca

Gère les cookies et l'authentification avec support pour:
- Import de cookies depuis un fichier
- Export de cookies pour backup
- Extraction de cookies depuis un navigateur
- Refresh automatique si possible
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime
import requests

from .exceptions import VoilaSessionExpired, VoilaAuthRequired


class SessionManager:
    """Gestion des sessions Voilà.ca"""
    
    BASE_URL = "https://voila.ca"
    SESSION_VERSION = 2  # For future migration
    
    def __init__(self, session_file: Optional[Path] = None):
        """
        Initialise le gestionnaire de session.
        
        Args:
            session_file: Chemin vers le fichier de session
        """
        self.session_file = Path(session_file).expanduser() if session_file else Path("~/.voila-session.json").expanduser()
        self._data: Dict[str, Any] = {
            'version': self.SESSION_VERSION,
            'cookies': [],
            'product_cache': {},
            'auth_status': 'unknown',
            'last_check': None
        }
        self._load()
    
    def _load(self) -> bool:
        """Charge la session depuis le fichier"""
        if not self.session_file.exists():
            return False
        
        try:
            with open(self.session_file) as f:
                data = json.load(f)
            
            # Handle old format (list of cookies)
            if isinstance(data, list):
                self._data = {
                    'version': self.SESSION_VERSION,
                    'cookies': data,
                    'product_cache': {},
                    'auth_status': 'unknown',
                    'last_check': None
                }
            else:
                self._data = data
                self._data.setdefault('version', 1)
                self._data.setdefault('product_cache', {})
                self._data.setdefault('auth_status', 'unknown')
            
            return True
        except Exception:
            return False
    
    def save(self) -> None:
        """Sauvegarde la session vers le fichier"""
        self.session_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.session_file, 'w') as f:
            json.dump(self._data, f, indent=2)
        
        self.session_file.chmod(0o600)
    
    @property
    def cookies(self) -> List[Dict]:
        """Retourne les cookies (format Playwright)"""
        return self._data.get('cookies', [])
    
    @cookies.setter
    def cookies(self, value: List[Dict]) -> None:
        """Définit les cookies"""
        self._data['cookies'] = value
        self._data['auth_status'] = 'unknown'
    
    @property
    def product_cache(self) -> Dict[str, str]:
        """Cache productId -> productName"""
        return self._data.get('product_cache', {})
    
    @product_cache.setter
    def product_cache(self, value: Dict[str, str]) -> None:
        """Définit le cache"""
        self._data['product_cache'] = value
    
    def get_cookies_dict(self) -> Dict[str, str]:
        """Retourne les cookies en format simple {name: value}"""
        return {c['name']: c['value'] for c in self.cookies}
    
    def import_cookies(self, source: Path) -> int:
        """
        Importe des cookies depuis un fichier.
        
        Formats supportés:
        - Playwright: [{name, value, domain, ...}, ...]
        - Simple: {name: value, ...}
        - HAR: {log: {entries: [{response: {cookies: [...]}}]}}
        
        Args:
            source: Chemin vers le fichier source
            
        Returns:
            Nombre de cookies importés
        """
        with open(source) as f:
            data = json.load(f)
        
        cookies = []
        
        # Detect format
        if isinstance(data, list):
            # Playwright format or list of cookies
            for c in data:
                if isinstance(c, dict) and 'name' in c:
                    cookies.append({
                        'name': c['name'],
                        'value': c['value'],
                        'domain': c.get('domain', '.voila.ca'),
                        'path': c.get('path', '/'),
                        'httpOnly': c.get('httpOnly', False),
                        'secure': c.get('secure', True)
                    })
        elif isinstance(data, dict):
            if 'cookies' in data:
                # Our format or EditThisCookie export
                return self.import_cookies_from_list(data['cookies'])
            elif 'log' in data:
                # HAR format
                for entry in data['log'].get('entries', []):
                    for c in entry.get('response', {}).get('cookies', []):
                        cookies.append({
                            'name': c['name'],
                            'value': c['value'],
                            'domain': c.get('domain', '.voila.ca'),
                            'path': c.get('path', '/'),
                            'httpOnly': c.get('httpOnly', False),
                            'secure': c.get('secure', True)
                        })
            else:
                # Simple {name: value} format
                for name, value in data.items():
                    cookies.append({
                        'name': name,
                        'value': str(value),
                        'domain': '.voila.ca',
                        'path': '/',
                        'secure': True
                    })
        
        self._data['cookies'] = cookies
        self._data['auth_status'] = 'unknown'
        self.save()
        
        return len(cookies)
    
    def import_cookies_from_list(self, cookies: List[Dict]) -> int:
        """Importe depuis une liste de cookies"""
        normalized = []
        for c in cookies:
            normalized.append({
                'name': c['name'],
                'value': c['value'],
                'domain': c.get('domain', '.voila.ca'),
                'path': c.get('path', '/'),
                'httpOnly': c.get('httpOnly', False),
                'secure': c.get('secure', True)
            })
        
        self._data['cookies'] = normalized
        self._data['auth_status'] = 'unknown'
        self.save()
        
        return len(normalized)
    
    def export_cookies(self, dest: Path, format: str = 'playwright') -> None:
        """
        Exporte les cookies vers un fichier.
        
        Args:
            dest: Chemin de destination
            format: 'playwright' ou 'simple'
        """
        if format == 'simple':
            data = self.get_cookies_dict()
        else:
            data = self.cookies
        
        with open(dest, 'w') as f:
            json.dump(data, f, indent=2)
    
    def is_authenticated(self) -> bool:
        """
        Vérifie si la session est authentifiée (met en cache le résultat).
        
        Returns:
            True si authentifié
        """
        # Check cache (valid for 5 minutes)
        if self._data.get('auth_status') in ('authenticated', 'anonymous'):
            last_check = self._data.get('last_check')
            if last_check:
                try:
                    last_dt = datetime.fromisoformat(last_check)
                    age = (datetime.now() - last_dt).total_seconds()
                    if age < 300:  # 5 minutes
                        return self._data['auth_status'] == 'authenticated'
                except:
                    pass
        
        # Actually check
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        })
        
        for c in self.cookies:
            session.cookies.set(c['name'], c['value'], domain=c.get('domain', '.voila.ca'))
        
        try:
            # Try to get customer info
            resp = session.get(f"{self.BASE_URL}/api/customer/v1/current", timeout=10)
            
            authenticated = resp.status_code == 200
            self._data['auth_status'] = 'authenticated' if authenticated else 'anonymous'
            self._data['last_check'] = datetime.now().isoformat()
            self.save()
            
            return authenticated
            
        except Exception:
            self._data['auth_status'] = 'unknown'
            return False
    
    def clear(self) -> None:
        """Efface la session"""
        self._data = {
            'version': self.SESSION_VERSION,
            'cookies': [],
            'product_cache': {},
            'auth_status': 'anonymous',
            'last_check': None
        }
        self.save()


def extract_cookies_instructions() -> str:
    """
    Retourne les instructions pour extraire les cookies manuellement.
    """
    return """
📋 **Comment extraire vos cookies Voilà.ca**

1. **Installez l'extension EditThisCookie** (Chrome/Firefox)
   - Chrome: https://chrome.google.com/webstore/detail/editthiscookie
   - Firefox: https://addons.mozilla.org/firefox/addon/etc2/

2. **Connectez-vous sur Voilà.ca** dans votre navigateur

3. **Exportez les cookies:**
   - Cliquez sur l'icône EditThisCookie
   - Cliquez sur "Export" (icône disquette)
   - Les cookies sont copiés dans le presse-papier

4. **Sauvegardez dans un fichier:**
   - Créez un fichier `~/voila-cookies.json`
   - Collez le contenu

5. **Importez dans voila-assistant:**
   ```
   ./voila import-cookies ~/voila-cookies.json
   ```

---

Alternative avec DevTools:
1. Ouvrez DevTools (F12) sur voila.ca
2. Onglet "Application" > Cookies
3. Sélectionnez voila.ca
4. Copiez manuellement les cookies essentiels:
   - gigya-* (tous les cookies gigya)
   - OptanonConsent
   - auth_* (si présent)
"""
