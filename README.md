# Voilà Assistant

Assistant IA pour commander sur Voilà.ca (IGA)

## Status

🚧 **En développement**

## Fonctionnalités prévues

- [x] Recherche de produits
- [ ] Gestion du panier (ajout/suppression)
- [ ] Authentification
- [ ] Récapitulatif de commande
- [ ] Intégration Telegram

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Voilà Assistant                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Telegram   │◄──►│    Core      │◄──►│   Voilà      │  │
│  │   Interface  │    │   Logic      │    │   Client     │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│                             │                    │          │
│                             ▼                    ▼          │
│                      ┌──────────────┐    ┌──────────────┐  │
│                      │   Session    │    │   Browser    │  │
│                      │   Manager    │    │   (Fallback) │  │
│                      └──────────────┘    └──────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Structure du projet

```
voila-assistant/
├── README.md              # Ce fichier
├── TODO.md                # Tâches détaillées
├── ARCHITECTURE.md        # Design détaillé
├── AGENTS.md              # Instructions pour agents IA
│
├── src/                   # Code source
│   ├── __init__.py
│   ├── client.py          # Client API Voilà
│   ├── search.py          # Recherche de produits
│   ├── cart.py            # Gestion du panier
│   ├── auth.py            # Authentification
│   ├── session.py         # Gestion des sessions/cookies
│   └── telegram.py        # Intégration Telegram
│
├── tests/                 # Tests unitaires
│   ├── test_search.py
│   ├── test_cart.py
│   └── test_auth.py
│
├── docs/                  # Documentation
│   ├── api-reference.md   # Endpoints découverts
│   └── setup.md           # Guide d'installation
│
├── scripts/               # Scripts utilitaires
│   └── export-cookies.js  # Export cookies browser
│
├── requirements.txt       # Dépendances Python
└── .env.example           # Template configuration
```

## Installation

```bash
cd ~/projects/voila-assistant
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## Usage

```bash
# Recherche
python -m src.search "lait 2%"

# Voir le panier
python -m src.cart show

# Ajouter au panier
python -m src.cart add <product_id> --quantity 2
```

## Configuration

Copier `.env.example` vers `.env` et configurer:

```bash
VOILA_SESSION_FILE=~/.secrets/voila-session.json
TELEGRAM_ENABLED=false
```

## Contribution

Ce projet est conçu pour être développé avec l'aide d'agents IA.
Voir `AGENTS.md` pour les instructions.

## Licence

Projet personnel - Usage privé uniquement
