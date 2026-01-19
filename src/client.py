"""
Client HTTP pour l'API Voilà
"""

import json
import time
from pathlib import Path
from typing import Optional, Dict, Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .exceptions import VoilaAPIError, VoilaSessionExpired


class VoilaClient:
    """Client HTTP pour interagir avec l'API Voilà.ca"""
    
    BASE_URL = "https://voila.ca"
    
    DEFAULT_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'fr-CA,fr;q=0.9,en-CA;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Origin': 'https://voila.ca',
        'Referer': 'https://voila.ca/',
    }
    
    def __init__(
        self,
        session_file: Optional[Path] = None,
        timeout: int = 30,
        max_retries: int = 3
    ):
        """
        Initialise le client Voilà.
        
        Args:
            session_file: Chemin vers le fichier de cookies (JSON)
            timeout: Timeout pour les requêtes en secondes
            max_retries: Nombre de retries en cas d'échec
        """
        self.session_file = session_file
        self.timeout = timeout
        self.session = self._create_session(max_retries)
        
        # Charger les cookies si fichier fourni
        if session_file:
            self.load_session(session_file)
    
    def _create_session(self, max_retries: int) -> requests.Session:
        """Crée une session avec retry automatique"""
        session = requests.Session()
        session.headers.update(self.DEFAULT_HEADERS)
        
        # Configurer retry
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        
        return session
    
    def load_session(self, path: Path) -> bool:
        """
        Charge les cookies depuis un fichier JSON.
        
        Args:
            path: Chemin vers le fichier de cookies
            
        Returns:
            True si chargé avec succès, False sinon
        """
        path = Path(path).expanduser()
        if not path.exists():
            return False
        
        try:
            with open(path, 'r') as f:
                cookies = json.load(f)
            
            for name, value in cookies.items():
                self.session.cookies.set(name, value)
            
            return True
        except (json.JSONDecodeError, IOError) as e:
            raise VoilaAPIError(f"Erreur chargement session: {e}")
    
    def save_session(self, path: Optional[Path] = None) -> None:
        """
        Sauvegarde les cookies vers un fichier JSON.
        
        Args:
            path: Chemin vers le fichier (utilise session_file par défaut)
        """
        path = Path(path or self.session_file).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        
        cookies = {c.name: c.value for c in self.session.cookies}
        
        with open(path, 'w') as f:
            json.dump(cookies, f, indent=2)
        
        # Sécuriser le fichier
        path.chmod(0o600)
    
    def get(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        Effectue une requête GET.
        
        Args:
            endpoint: Endpoint API (ex: /api/cart/v1/carts/active)
            **kwargs: Arguments supplémentaires pour requests
            
        Returns:
            Réponse JSON parsée
            
        Raises:
            VoilaAPIError: En cas d'erreur HTTP
            VoilaSessionExpired: Si session invalide
        """
        url = f"{self.BASE_URL}{endpoint}"
        return self._request('GET', url, **kwargs)
    
    def post(self, endpoint: str, data: Any = None, **kwargs) -> Dict[str, Any]:
        """
        Effectue une requête POST.
        
        Args:
            endpoint: Endpoint API
            data: Données à envoyer (sera converti en JSON)
            **kwargs: Arguments supplémentaires pour requests
            
        Returns:
            Réponse JSON parsée
            
        Raises:
            VoilaAPIError: En cas d'erreur HTTP
        """
        url = f"{self.BASE_URL}{endpoint}"
        return self._request('POST', url, json=data, **kwargs)
    
    def put(self, endpoint: str, data: Any = None, **kwargs) -> Dict[str, Any]:
        """
        Effectue une requête PUT.
        
        Args:
            endpoint: Endpoint API
            data: Données à envoyer
            **kwargs: Arguments supplémentaires
            
        Returns:
            Réponse JSON parsée
        """
        url = f"{self.BASE_URL}{endpoint}"
        return self._request('PUT', url, json=data, **kwargs)
    
    def delete(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        Effectue une requête DELETE.
        
        Args:
            endpoint: Endpoint API
            **kwargs: Arguments supplémentaires
            
        Returns:
            Réponse JSON parsée
        """
        url = f"{self.BASE_URL}{endpoint}"
        return self._request('DELETE', url, **kwargs)
    
    def _request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """
        Effectue une requête HTTP.
        
        Args:
            method: Méthode HTTP (GET, POST, etc.)
            url: URL complète
            **kwargs: Arguments pour requests
            
        Returns:
            Réponse JSON parsée
            
        Raises:
            VoilaAPIError: En cas d'erreur
            VoilaSessionExpired: Si 401/403 indiquant session expirée
        """
        kwargs.setdefault('timeout', self.timeout)
        
        try:
            response = self.session.request(method, url, **kwargs)
            
            # Gérer les erreurs d'authentification
            if response.status_code in (401, 403):
                # Vérifier si c'est une session expirée
                try:
                    error_data = response.json()
                    if 'session' in str(error_data).lower() or 'auth' in str(error_data).lower():
                        raise VoilaSessionExpired("Session expirée, re-login nécessaire")
                except json.JSONDecodeError:
                    pass
                raise VoilaAPIError(
                    f"Accès refusé: {response.status_code}",
                    status_code=response.status_code
                )
            
            # Lever une exception pour les autres erreurs HTTP
            response.raise_for_status()
            
            # Parser la réponse JSON
            if response.content:
                return response.json()
            return {}
            
        except requests.exceptions.Timeout:
            raise VoilaAPIError("Timeout lors de la requête")
        except requests.exceptions.ConnectionError:
            raise VoilaAPIError("Erreur de connexion")
        except requests.exceptions.HTTPError as e:
            raise VoilaAPIError(
                f"Erreur HTTP: {e}",
                status_code=e.response.status_code if e.response else None
            )
        except json.JSONDecodeError:
            raise VoilaAPIError("Réponse JSON invalide")
    
    def is_session_valid(self) -> bool:
        """
        Vérifie si la session est valide en faisant une requête test.
        
        Returns:
            True si la session est valide
        """
        try:
            self.get('/api/cart/v1/carts/active')
            return True
        except (VoilaSessionExpired, VoilaAPIError):
            return False
    
    def get_cookies(self) -> Dict[str, str]:
        """Retourne les cookies actuels"""
        return {c.name: c.value for c in self.session.cookies}
    
    def set_cookies(self, cookies: Dict[str, str]) -> None:
        """Définit les cookies"""
        for name, value in cookies.items():
            self.session.cookies.set(name, value)
