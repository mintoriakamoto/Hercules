"""Long-term memory tool — store and retrieve information across sessions."""

import json
from datetime import datetime

import logging

logger = logging.getLogger(__name__)

from tools.registry import registry

# Schema for memory tool
MEMORY_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "description": "Action to perform",
            "enum": ["store", "recall", "search", "delete", "list"],
        },
        "key": {
            "type": "string",
            "description": "Memory key (for store/recall/delete actions)",
        },
        "value": {
            "type": "string",
            "description": "Value to store (JSON string for complex data)",
        },
        "query": {
            "type": "string",
            "description": "Search query (for search action)",
        },
        "limit": {
            "type": "integer",
            "description": "Max results to return",
            "default": 10,
            "minimum": 1,
            "maximum": 100,
        },
    },
    "required": ["action"],
}


def memory_tool(action, key=None, value=None, query=None, limit=10):
    """Store and retrieve long-term memory across sessions."""
    
    try:
        from hercules_state import SessionDB
        
        db = SessionDB()
        
        if action == "store":
            if not key or value is None:
                return {"error": "action=store requires key and value"}
            
            try:
                # Try to parse value as JSON if it's a string
                if isinstance(value, str):
                    parsed_value = json.loads(value)
                else:
                    parsed_value = value
            except:
                parsed_value = value
            
            # Store in memory table
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS memory (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
                """,
            )
            db.execute(
                """
                INSERT OR REPLACE INTO memory (key, value, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (key, json.dumps(parsed_value), datetime.now().isoformat(), datetime.now().isoformat()),
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
            
            # Simple substring search in memory keys
            results = db.execute(
                "SELECT key, value, updated_at FROM memory WHERE key LIKE ? ORDER BY updated_at DESC LIMIT ?",
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
                "count": len(results),
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


registry.register(
    name="memory",
    toolset="memory",
    schema=MEMORY_SCHEMA,
    handler=lambda args, **kw: memory_tool(
        action=args.get("action", ""),
        key=args.get("key"),
        value=args.get("value"),
        query=args.get("query"),
        limit=args.get("limit", 10),
    ),
    check_fn=lambda: True,  # Always available
    emoji="🧠",
)
