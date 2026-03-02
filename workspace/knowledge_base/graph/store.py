"""
Knowledge Graph Store
Simple entity-relationship store with JSONL backend
"""
import json
import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

QUIESCE_ENV = "OPENCLAW_QUIESCE"
_PROTECTED_SUFFIXES = (
    "MEMORY.md",
    "workspace/knowledge_base/data/entities.jsonl",
    "workspace/knowledge_base/data/last_sync.txt",
    "workspace/state/tacti_cr/events.jsonl",
)


def _is_quiesced() -> bool:
    return os.getenv(QUIESCE_ENV) == "1"


def _is_protected_target(path: Path) -> bool:
    resolved = str(path.resolve()).replace("\\", "/")
    for suffix in _PROTECTED_SUFFIXES:
        if resolved.endswith(suffix):
            return True
    return False


def _allow_write(path: Path) -> bool:
    if _is_quiesced() and _is_protected_target(path):
        print(f"QUIESCED: skipping write to {path}")
        return False
    return True


class KnowledgeGraphStore:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.entities_path = self.data_dir / "entities.jsonl"
        self.relations_path = self.data_dir / "relations.jsonl"
        
        self.entities_path.parent.mkdir(parents=True, exist_ok=True)
        
        if not self.entities_path.exists() and _allow_write(self.entities_path):
            self.entities_path.touch()
        if not self.relations_path.exists():
            self.relations_path.touch()
    
    def _load_entities(self) -> List[Dict]:
        entities = []
        with open(self.entities_path) as f:
            for line in f:
                if line.strip():
                    entities.append(json.loads(line))
        return entities
    
    def _save_entity(self, entity: Dict):
        if not _allow_write(self.entities_path):
            return
        with open(self.entities_path, "a") as f:
            f.write(json.dumps(entity, ensure_ascii=False) + "\n")
    
    def add_entity(
        self,
        name: str,
        entity_type: str,
        content: str,
        source: str = "manual",
        metadata: Optional[Dict] = None
    ) -> str:
        """Add an entity to the knowledge graph."""
        # Generate ID
        entity_id = hashlib.sha256(
            f"{name}{entity_type}{datetime.now(timezone.utc).isoformat()}".encode()
        ).hexdigest()[:12]
        
        entity = {
            "id": entity_id,
            "name": name,
            "entity_type": entity_type,
            "content": content,
            "source": source,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "relations": []
        }
        
        self._save_entity(entity)
        return entity_id
    
    def get_entity(self, name: str) -> List[Dict]:
        """Get entities by name (fuzzy match)."""
        entities = self._load_entities()
        name_lower = name.lower()
        return [e for e in entities if name_lower in e["name"].lower()]
    
    def all_entities(self, limit: int = 20) -> List[Dict]:
        """Get all entities, newest first."""
        entities = self._load_entities()
        entities.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return entities[:limit]
    
    def add_relation(
        self,
        from_id: str,
        to_id: str,
        relation_type: str,
        metadata: Optional[Dict] = None
    ):
        """Add a relationship between entities."""
        relation = {
            "from_id": from_id,
            "to_id": to_id,
            "relation_type": relation_type,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        with open(self.relations_path, "a") as f:
            f.write(json.dumps(relation, ensure_ascii=False) + "\n")
        
        # Update entity with relation
        entities = self._load_entities()
        for e in entities:
            if e["id"] == from_id:
                e.setdefault("relations", []).append({
                    "to": to_id,
                    "type": relation_type
                })
        
        # Rewrite entities
        if not _allow_write(self.entities_path):
            return
        with open(self.entities_path, "w") as f:
            for e in entities:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
    
    def get_relations(self, entity_id: str) -> List[Dict]:
        """Get all relations for an entity."""
        relations = []
        with open(self.relations_path) as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    if r["from_id"] == entity_id or r["to_id"] == entity_id:
                        relations.append(r)
        return relations
    
    def find_related(self, entity_id: str, relation_type: Optional[str] = None) -> List[Dict]:
        """Find related entities."""
        relations = self.get_relations(entity_id)
        
        entities = {e["id"]: e for e in self._load_entities()}
        
        results = []
        for r in relations:
            if r["from_id"] == entity_id:
                target_id = r["to_id"]
            else:
                target_id = r["from_id"]
            
            if target_id in entities:
                entity = entities[target_id]
                if relation_type is None or r["relation_type"] == relation_type:
                    results.append({
                        "entity": entity,
                        "relation": r["relation_type"]
                    })
        
        return results
    
    def stats(self) -> Dict:
        """Get statistics."""
        entities = self._load_entities()
        
        relations = []
        with open(self.relations_path) as f:
            for line in f:
                if line.strip():
                    relations.append(json.loads(line))
        
        # Count by type
        type_counts = {}
        for e in entities:
            t = e.get("entity_type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1
        
        return {
            "total": len(entities),
            "relations": len(relations),
            "by_type": type_counts
        }
    
    def search(self, query: str, limit: int = 5) -> List[Dict]:
        """Simple keyword search."""
        entities = self._load_entities()
        query_lower = query.lower()
        
        results = []
        for e in entities:
            score = 0
            if query_lower in e["name"].lower():
                score += 10
            if query_lower in e["content"].lower():
                score += 5
            if query_lower in e.get("entity_type", "").lower():
                score += 3
            
            if score > 0:
                results.append((score, e))
        
        results.sort(key=lambda x: x[0], reverse=True)
        return [r[1] for r in results[:limit]]
