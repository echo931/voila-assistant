"""
Module de gestion des besoins d'épicerie pour Voilà Assistant.

Permet de créer une liste de besoins persistante que différents membres
du foyer peuvent alimenter, et qui sera compilée lors de la prochaine épicerie.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, Literal
from dataclasses import dataclass, asdict, field


DEFAULT_NEEDS_PATH = Path("~/.voila-needs.json").expanduser()

# Types
Priority = Literal["low", "normal", "high", "urgent"]
NeedStatus = Literal["pending", "done", "cancelled"]


@dataclass
class NeedItem:
    """Un besoin d'épicerie"""
    id: str
    item: str
    quantity: float = 1.0
    unit: Optional[str] = None
    priority: Priority = "normal"
    added_by: str = "Mathieu"
    added_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    notes: Optional[str] = None
    status: NeedStatus = "pending"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NeedItem":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            item=data.get("item", ""),
            quantity=data.get("quantity", 1.0),
            unit=data.get("unit"),
            priority=data.get("priority", "normal"),
            added_by=data.get("added_by", "Mathieu"),
            added_at=data.get("added_at", datetime.now(timezone.utc).isoformat()),
            notes=data.get("notes"),
            status=data.get("status", "pending")
        )
    
    def format_line(self, include_meta: bool = False) -> str:
        """Formate l'item en une ligne lisible"""
        # Quantité et unité
        qty_str = ""
        if self.quantity != 1 or self.unit:
            qty_str = f" ×{self.quantity:g}"
            if self.unit:
                qty_str = f" ({self.quantity:g} {self.unit})"
        
        # Priorité
        priority_icon = {
            "low": "⬇️",
            "normal": "",
            "high": "⬆️",
            "urgent": "🔴"
        }.get(self.priority, "")
        
        line = f"{priority_icon}{self.item}{qty_str}".strip()
        
        if include_meta:
            meta_parts = []
            if self.added_by != "Mathieu":
                meta_parts.append(f"par {self.added_by}")
            if self.notes:
                meta_parts.append(self.notes)
            if meta_parts:
                line += f" — {', '.join(meta_parts)}"
        
        return line


class NeedsManager:
    """
    Gestionnaire de la liste de besoins d'épicerie.
    
    Permet d'ajouter/retirer des besoins, les marquer comme faits,
    et compiler la liste pour l'épicerie.
    """
    
    def __init__(self, needs_path: Optional[Path] = None):
        """
        Initialise le gestionnaire.
        
        Args:
            needs_path: Chemin vers le fichier JSON des besoins
        """
        self.needs_path = Path(needs_path or DEFAULT_NEEDS_PATH).expanduser()
        self._data: Optional[Dict[str, Any]] = None
    
    @property
    def data(self) -> Dict[str, Any]:
        """Charge les données depuis le fichier si nécessaire"""
        if self._data is None:
            self._data = self._load()
        return self._data
    
    def _load(self) -> Dict[str, Any]:
        """Charge les données depuis le fichier JSON"""
        if self.needs_path.exists():
            try:
                with open(self.needs_path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, KeyError):
                pass
        return {
            "needs": [],
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
    
    def _save(self) -> None:
        """Sauvegarde les données vers le fichier JSON"""
        self.data["last_updated"] = datetime.now(timezone.utc).isoformat()
        self.needs_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.needs_path, 'w') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
    
    def _get_needs(self) -> List[NeedItem]:
        """Retourne la liste des NeedItem"""
        return [NeedItem.from_dict(n) for n in self.data.get("needs", [])]
    
    def _save_needs(self, needs: List[NeedItem]) -> None:
        """Sauvegarde la liste des NeedItem"""
        self.data["needs"] = [n.to_dict() for n in needs]
        self._save()
    
    def add_need(
        self,
        item: str,
        quantity: float = 1.0,
        unit: Optional[str] = None,
        priority: Priority = "normal",
        added_by: str = "Mathieu",
        notes: Optional[str] = None
    ) -> NeedItem:
        """
        Ajoute un besoin à la liste.
        
        Si l'item existe déjà en pending, augmente la quantité.
        
        Args:
            item: Nom de l'item (ex: "lait", "céréales")
            quantity: Quantité souhaitée
            unit: Unité (ex: "L", "kg", "boîtes")
            priority: Priorité (low/normal/high/urgent)
            added_by: Qui a ajouté ce besoin
            notes: Notes additionnelles
            
        Returns:
            Le NeedItem créé ou mis à jour
        """
        needs = self._get_needs()
        item_lower = item.strip().lower()
        
        # Chercher si le besoin existe déjà en pending
        for need in needs:
            if need.item.lower() == item_lower and need.status == "pending":
                # Mettre à jour la quantité
                need.quantity += quantity
                # Prendre la priorité la plus haute
                priorities = ["low", "normal", "high", "urgent"]
                if priorities.index(priority) > priorities.index(need.priority):
                    need.priority = priority
                # Ajouter les notes
                if notes:
                    if need.notes:
                        need.notes += f"; {notes}"
                    else:
                        need.notes = notes
                self._save_needs(needs)
                return need
        
        # Créer un nouveau besoin
        new_need = NeedItem(
            id=str(uuid.uuid4()),
            item=item.strip(),
            quantity=quantity,
            unit=unit,
            priority=priority,
            added_by=added_by,
            notes=notes
        )
        needs.append(new_need)
        self._save_needs(needs)
        return new_need
    
    def remove_need(self, item_or_id: str) -> bool:
        """
        Retire un besoin de la liste.
        
        Args:
            item_or_id: Nom de l'item ou son ID
            
        Returns:
            True si l'item a été retiré, False si non trouvé
        """
        needs = self._get_needs()
        item_lower = item_or_id.strip().lower()
        
        for i, need in enumerate(needs):
            if need.id == item_or_id or need.item.lower() == item_lower:
                del needs[i]
                self._save_needs(needs)
                return True
        
        return False
    
    def list_needs(
        self,
        status: Optional[NeedStatus] = "pending",
        by: Optional[str] = None
    ) -> List[NeedItem]:
        """
        Liste les besoins selon les critères.
        
        Args:
            status: Filtrer par statut (None = tous)
            by: Filtrer par personne qui a ajouté
            
        Returns:
            Liste des NeedItem correspondants
        """
        needs = self._get_needs()
        
        if status:
            needs = [n for n in needs if n.status == status]
        
        if by:
            by_lower = by.lower()
            needs = [n for n in needs if n.added_by.lower() == by_lower]
        
        # Trier par priorité (urgent > high > normal > low) puis par date
        priority_order = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
        needs.sort(key=lambda n: (priority_order.get(n.priority, 2), n.added_at))
        
        return needs
    
    def mark_done(self, item_or_id: str) -> Optional[NeedItem]:
        """
        Marque un besoin comme acheté.
        
        Args:
            item_or_id: Nom de l'item ou son ID
            
        Returns:
            Le NeedItem mis à jour, ou None si non trouvé
        """
        needs = self._get_needs()
        item_lower = item_or_id.strip().lower()
        
        for need in needs:
            if need.id == item_or_id or need.item.lower() == item_lower:
                need.status = "done"
                self._save_needs(needs)
                return need
        
        return None
    
    def mark_all_done(self) -> int:
        """
        Marque tous les besoins pending comme done.
        
        Returns:
            Nombre de besoins marqués
        """
        needs = self._get_needs()
        count = 0
        
        for need in needs:
            if need.status == "pending":
                need.status = "done"
                count += 1
        
        if count > 0:
            self._save_needs(needs)
        
        return count
    
    def clear_done(self) -> int:
        """
        Supprime les besoins complétés.
        
        Returns:
            Nombre de besoins supprimés
        """
        needs = self._get_needs()
        initial_count = len(needs)
        needs = [n for n in needs if n.status != "done"]
        removed = initial_count - len(needs)
        
        if removed > 0:
            self._save_needs(needs)
        
        return removed
    
    def get_by_id(self, need_id: str) -> Optional[NeedItem]:
        """Retourne un besoin par son ID"""
        for need in self._get_needs():
            if need.id == need_id:
                return need
        return None
    
    def get_by_item(self, item: str, status: Optional[NeedStatus] = "pending") -> Optional[NeedItem]:
        """Retourne un besoin par son nom d'item"""
        item_lower = item.strip().lower()
        for need in self._get_needs():
            if need.item.lower() == item_lower:
                if status is None or need.status == status:
                    return need
        return None
    
    def compile_list(self) -> str:
        """
        Compile la liste des besoins pending en format texte pour l'épicerie.
        
        Returns:
            Liste formatée prête pour l'épicerie
        """
        needs = self.list_needs(status="pending")
        
        if not needs:
            return "📋 Aucun besoin en attente"
        
        lines = [f"📋 Liste d'épicerie ({len(needs)} articles)", ""]
        
        # Grouper par priorité
        urgent = [n for n in needs if n.priority == "urgent"]
        high = [n for n in needs if n.priority == "high"]
        normal = [n for n in needs if n.priority == "normal"]
        low = [n for n in needs if n.priority == "low"]
        
        if urgent:
            lines.append("🔴 URGENT:")
            for n in urgent:
                lines.append(f"  • {n.format_line(include_meta=True)}")
            lines.append("")
        
        if high:
            lines.append("⬆️ Priorité haute:")
            for n in high:
                lines.append(f"  • {n.format_line(include_meta=True)}")
            lines.append("")
        
        if normal or low:
            lines.append("📝 À acheter:")
            for n in normal + low:
                lines.append(f"  • {n.format_line(include_meta=True)}")
        
        return "\n".join(lines).strip()
    
    def format_summary(self) -> str:
        """Formate la liste des besoins pour affichage"""
        needs = self.list_needs(status="pending")
        
        if not needs:
            return "📋 Aucun besoin en attente"
        
        lines = [f"📋 Besoins en attente ({len(needs)} articles)", ""]
        
        for i, need in enumerate(needs, 1):
            lines.append(f"  {i}. {need.format_line(include_meta=True)}")
        
        return "\n".join(lines)
    
    def format_telegram(self) -> str:
        """Formate la liste pour Telegram (HTML)"""
        needs = self.list_needs(status="pending")
        
        if not needs:
            return "📋 <b>Aucun besoin en attente</b>"
        
        lines = [f"📋 <b>Besoins en attente</b> ({len(needs)} articles)\n"]
        
        for i, need in enumerate(needs, 1):
            line = f"{i}. {need.format_line()}"
            lines.append(line)
        
        return "\n".join(lines)
    
    def to_local_cart_items(self) -> List[Dict[str, Any]]:
        """
        Convertit les besoins pending en items pour le panier local.
        
        Returns:
            Liste de dicts {query, quantity} prêts pour LocalCartManager
        """
        needs = self.list_needs(status="pending")
        items = []
        
        for need in needs:
            items.append({
                "query": need.item,
                "quantity": int(need.quantity) if need.quantity == int(need.quantity) else 1
            })
        
        return items
