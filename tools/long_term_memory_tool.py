"""Long-term memory tool — store and retrieve information across sessions."""

import logging
import json
from typing import Any, Dict, Optional, List
from pathlib import Path
from datetime import datetime

from tools.registry import register_tool

logger = logging.getLogger(__name__)


@register_tool(name="memory")
def memory(
    action: str,
    key: Optional[str] = None,
    value: Optional[Any] = None,
    query: Optional[str] = None,
    limit: int = 10,
) -> Dict[str, Any]:
    """
    Store and retrieve long-term memory across sessions.
    
    Args:
        action: Action to perform ("store", "recall", "search", "delete", "list")
        key: Memory key (for store/recall/delete)
        value: Value to store (for store action)
        query: Search query (for search action)
        limit: Max results to return (for search/list)
    
    Returns:
        Dict with results
    """
    try:
        from hercules_state import SessionDB
        
        db = SessionDB()
        
        if action == "store":
            if not key or value is None:
                return {"error": "action=store requires key and value"}
            
            # Store in memory table
            db.execute(
                """
                INSERT OR REPLACE INTO memory (key, value, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (key, json.dumps(value), datetime.now().isoformat(), datetime.now().isoformat()),
            )
            return {
                "action": "store",
                "key": key,
                "stored": True,
                "timestamp": datetime.now().isoformat(),
            }
        
        elif action == "recall":
            if not key:
                return {"error": "action=recall requires key"}
            
            result = db.execute(
                "SELECT value, updated_at FROM memory WHERE key = ?",
                (key,),
            ).fetchone()
            
            if not result:
                return {"error": f"Memory key not found: {key}"}
            
            return {
                "action": "recall",
                "key": key,
                "value": json.loads(result[0]),
                "updated_at": result[1],
            }
        
        elif action == "search":
            if not query:
                return {"error": "action=search requires query"}
            
            # Simple substring search in memory
            results = db.execute(
                "SELECT key, value, updated_at FROM memory WHERE key LIKE ? LIMIT ?",
                (f"%{query}%", limit),
            ).fetchall()
            
            return {
                "action": "search",
                "query": query,
                "results": [
                    {
                        "key": r[0],
                        "value": json.loads(r[1]),
                        "updated_at": r[2],
                    }
                    for r in results
                ],
            }
        
        elif action == "delete":
            if not key:
                return {"error": "action=delete requires key"}
            
            db.execute("DELETE FROM memory WHERE key = ?", (key,))
            return {
                "action": "delete",
                "key": key,
                "deleted": True,
            }
        
        elif action == "list":
            results = db.execute(
                "SELECT key, updated_at FROM memory ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            
            return {
                "action": "list",
                "count": len(results),
                "memories": [
                    {
                        "key": r[0],
                        "updated_at": r[1],
                    }
                    for r in results
                ],
            }
        
        else:
            return {
                "error": f"Unknown action: {action}. Use: store, recall, search, delete, list"
            }
    
    except Exception as e:
        return {"error": str(e)}
