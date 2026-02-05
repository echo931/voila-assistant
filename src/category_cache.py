"""Category tree cache for Voilà.

Crawls the full category hierarchy once and caches it locally.
Allows instant lookups without browser automation.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

DEFAULT_CACHE_FILE = Path.home() / ".voila-categories.json"


@dataclass
class Category:
    """A category node in the tree."""
    name: str
    slug: str
    id: str
    path: str  # Full path like "dairy-eggs/milk/flavoured-milk"
    children: List['Category'] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "slug": self.slug,
            "id": self.id,
            "path": self.path,
            "children": [c.to_dict() for c in self.children]
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Category':
        return cls(
            name=data["name"],
            slug=data["slug"],
            id=data["id"],
            path=data["path"],
            children=[cls.from_dict(c) for c in data.get("children", [])]
        )


@dataclass 
class CategoryCache:
    """Manages the category tree cache."""
    
    cache_file: Path = DEFAULT_CACHE_FILE
    categories: List[Category] = field(default_factory=list)
    last_updated: Optional[str] = None
    _flat_index: Dict[str, Category] = field(default_factory=dict, repr=False)
    
    def __post_init__(self):
        self.load()
    
    def load(self) -> bool:
        """Load cache from file. Returns True if loaded."""
        if not self.cache_file.exists():
            return False
        
        try:
            data = json.loads(self.cache_file.read_text())
            self.categories = [Category.from_dict(c) for c in data.get("categories", [])]
            self.last_updated = data.get("last_updated")
            self._build_index()
            return True
        except Exception as e:
            logger.warning(f"Failed to load category cache: {e}")
            return False
    
    def save(self) -> None:
        """Save cache to file."""
        data = {
            "last_updated": self.last_updated,
            "categories": [c.to_dict() for c in self.categories]
        }
        self.cache_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    
    def _build_index(self) -> None:
        """Build flat index for fast lookups."""
        self._flat_index = {}
        
        def index_category(cat: Category):
            # Index by path, slug, name (lowercase)
            self._flat_index[cat.path] = cat
            self._flat_index[cat.slug] = cat
            self._flat_index[cat.name.lower()] = cat
            for child in cat.children:
                index_category(child)
        
        for cat in self.categories:
            index_category(cat)
    
    def find(self, query: str) -> Optional[Category]:
        """Find a category by path, slug, or name."""
        query_lower = query.lower().strip()
        
        # Direct match
        if query_lower in self._flat_index:
            return self._flat_index[query_lower]
        
        # Partial match on name
        for key, cat in self._flat_index.items():
            if query_lower in cat.name.lower():
                return cat
        
        return None
    
    def get_all_flat(self) -> List[Category]:
        """Get all categories as a flat list."""
        result = []
        
        def collect(cat: Category, depth: int = 0):
            result.append((cat, depth))
            for child in cat.children:
                collect(child, depth + 1)
        
        for cat in self.categories:
            collect(cat)
        
        return result
    
    def refresh(self, headless: bool = True, timeout: int = 30000, max_depth: int = 3, 
                on_progress: Optional[callable] = None) -> int:
        """Crawl and refresh the full category tree. Returns category count.
        
        Args:
            headless: Run browser headless
            timeout: Page load timeout
            max_depth: Maximum depth to crawl (default 3)
            on_progress: Callback(message) for progress updates
        """
        BASE_URL = "https://voila.ca"
        
        def log(msg):
            if on_progress:
                on_progress(msg)
            logger.info(msg)
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context()
            page = context.new_page()
            
            # Get top-level categories
            log("Fetching top-level categories...")
            page.goto(f"{BASE_URL}/categories", wait_until="domcontentloaded", timeout=timeout)
            page.wait_for_timeout(2000)
            
            top_cats = page.evaluate('''
                () => {
                    const links = document.querySelectorAll('a[href*="/categories/"]');
                    const seen = new Set();
                    const results = [];
                    
                    for (const link of links) {
                        const href = link.getAttribute('href');
                        const match = href.match(/\\/categories\\/([^\\/]+)\\/([A-Z0-9]+)/);
                        if (match && !seen.has(match[2])) {
                            seen.add(match[2]);
                            results.push({
                                name: link.textContent?.trim() || match[1],
                                slug: match[1],
                                id: match[2]
                            });
                        }
                    }
                    return results;
                }
            ''')
            
            log(f"Found {len(top_cats)} top-level categories")
            
            self.categories = []
            total_count = 0
            
            for i, top in enumerate(top_cats):
                log(f"[{i+1}/{len(top_cats)}] Crawling {top['name']}...")
                cat = Category(
                    name=top['name'],
                    slug=top['slug'],
                    id=top['id'],
                    path=top['slug']
                )
                
                # Crawl children recursively
                self._crawl_children(page, cat, BASE_URL, timeout, max_depth, log)
                self.categories.append(cat)
                total_count += self._count_categories(cat)
            
            browser.close()
        
        self.last_updated = datetime.utcnow().isoformat()
        self._build_index()
        self.save()
        
        return total_count
    
    def _crawl_children(self, page, parent: Category, base_url: str, timeout: int, 
                        max_depth: int = 3, log: callable = None) -> None:
        """Recursively crawl child categories."""
        if max_depth <= 0:
            return
        
        url = f"{base_url}/categories/{parent.path}/{parent.id}"
        
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            page.wait_for_timeout(1000)
            
            # Find direct children (one level deeper)
            parent_path = parent.path
            children = page.evaluate(f'''
                () => {{
                    const links = document.querySelectorAll('a[href*="/categories/"]');
                    const seen = new Set();
                    const results = [];
                    const parentPath = "{parent_path}";
                    
                    for (const link of links) {{
                        const href = link.getAttribute('href');
                        const escapedPath = parentPath.replace(/\\//g, '\\\\/');
                        const pattern = new RegExp('/categories/' + escapedPath + '/([^/?]+)/([A-Z0-9]+)');
                        const match = href.match(pattern);
                        if (match && !seen.has(match[2])) {{
                            seen.add(match[2]);
                            results.push({{
                                name: link.textContent?.trim() || match[1],
                                slug: match[1],
                                id: match[2]
                            }});
                        }}
                    }}
                    return results;
                }}
            ''')
            
            for child_data in children:
                child = Category(
                    name=child_data['name'],
                    slug=child_data['slug'],
                    id=child_data['id'],
                    path=f"{parent.path}/{child_data['slug']}"
                )
                parent.children.append(child)
                
                # Recurse (only if we have depth left)
                if max_depth > 1:
                    self._crawl_children(page, child, base_url, timeout, max_depth - 1, log)
                
        except Exception as e:
            logger.debug(f"Error crawling {parent.path}: {e}")
    
    def _count_categories(self, cat: Category) -> int:
        """Count total categories including children."""
        count = 1
        for child in cat.children:
            count += self._count_categories(child)
        return count
    
    def format_tree(self) -> str:
        """Format category tree for display."""
        lines = []
        
        def format_cat(cat: Category, prefix: str = "", is_last: bool = True):
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{cat.name} ({cat.id})")
            
            child_prefix = prefix + ("    " if is_last else "│   ")
            for i, child in enumerate(cat.children):
                format_cat(child, child_prefix, i == len(cat.children) - 1)
        
        for i, cat in enumerate(self.categories):
            format_cat(cat, "", i == len(self.categories) - 1)
        
        return "\n".join(lines)
