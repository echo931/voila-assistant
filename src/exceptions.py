"""
Exceptions personnalisées pour Voilà Assistant
"""


class VoilaError(Exception):
    """Erreur de base pour toutes les erreurs Voilà"""
    pass


class VoilaAPIError(VoilaError):
    """Erreur lors d'un appel API"""
    
    def __init__(self, message: str, status_code: int = None, response: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class VoilaAuthError(VoilaError):
    """Erreur d'authentification"""
    pass


class VoilaSessionExpired(VoilaAuthError):
    """Session expirée, re-login nécessaire"""
    pass


class VoilaProductNotFound(VoilaError):
    """Produit introuvable"""
    
    def __init__(self, product_id: str):
        super().__init__(f"Produit introuvable: {product_id}")
        self.product_id = product_id


class VoilaBrowserError(VoilaError):
    """Erreur lors de l'utilisation du browser"""
    pass


class VoilaCartError(VoilaError):
    """Erreur lors d'une opération sur le panier"""
    pass
