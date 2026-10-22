/// Ultra-fast tool execution engines
///
/// Combines terminal_tool, delegate_tool, and mcp_tool optimizations.
/// Hot-path: all tools called frequently during agent execution.

use std::sync::Arc;
use std::collections::HashMap;

/// Terminal command execution (zero-copy)
#[derive(Clone, Debug)]
pub struct TerminalCommand {
    pub command: Arc<str>,
    pub args: Vec<Arc<str>>,
    pub timeout_ms: u32,
}

impl TerminalCommand {
    pub fn new(command: impl Into<String>) -> Self {
        TerminalCommand {
            command: Arc::from(command.into()),
            args: Vec::new(),
            timeout_ms: 30000,
        }
    }

    pub fn with_args(mut self, args: Vec<impl Into<String>>) -> Self {
        self.args = args.into_iter().map(|a| Arc::from(a.into())).collect();
        self
    }
}

/// Terminal execution result
#[derive(Clone, Debug)]
pub struct TerminalResult {
    pub success: bool,
    pub stdout: Arc<str>,
    pub stderr: Arc<str>,
    pub exit_code: i32,
}

/// MCP tool request (JSON protocol)
#[derive(Clone, Debug)]
pub struct MCPRequest {
    pub method: Arc<str>,
    pub params: Arc<str>,
    pub request_id: u64,
}

impl MCPRequest {
    pub fn new(method: impl Into<String>, params: impl Into<String>) -> Self {
        static ID_COUNTER: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
        MCPRequest {
            method: Arc::from(method.into()),
            params: Arc::from(params.into()),
            request_id: ID_COUNTER.fetch_add(1, std::sync::atomic::Ordering::Relaxed),
        }
    }
}

/// MCP tool response
#[derive(Clone, Debug)]
pub struct MCPResponse {
    pub request_id: u64,
    pub result: Arc<str>,
    pub error: Option<Arc<str>>,
}

/// Subagent delegation task
#[derive(Clone, Debug)]
pub struct DelegatedTask {
    pub task_id: Arc<str>,
    pub agent_id: Arc<str>,
    pub prompt: Arc<str>,
    pub max_retries: u32,
}

impl DelegatedTask {
    pub fn new(
        agent_id: impl Into<String>,
        prompt: impl Into<String>,
    ) -> Self {
        let task_id = format!("task_{}", uuid::Uuid::new_v4());
        DelegatedTask {
            task_id: Arc::from(task_id),
            agent_id: Arc::from(agent_id.into()),
            prompt: Arc::from(prompt.into()),
            max_retries: 1,
        }
    }
}

/// Fast tool router (O(1))
pub struct ToolRouter {
    tools: Arc<HashMap<String, Arc<str>>>,
}

impl ToolRouter {
    pub fn new() -> Self {
        ToolRouter {
            tools: Arc::new(HashMap::new()),
        }
    }

    /// Route to correct tool handler (O(1))
    pub fn route(&self, tool_name: &str) -> Option<Arc<str>> {
        self.tools.get(tool_name).cloned()
    }

    /// Register tool (O(1) insert)
    pub fn register(&mut self, name: impl Into<String>, handler: impl Into<String>) {
        let name = name.into();
        let handler = Arc::from(handler.into());
        Arc::get_mut(&mut self.tools)
            .expect("tools lock")
            .insert(name, handler);
    }
}

impl Clone for ToolRouter {
    fn clone(&self) -> Self {
        ToolRouter {
            tools: Arc::clone(&self.tools),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_terminal_command() {
        let cmd = TerminalCommand::new("ls")
            .with_args(vec!["-la"]);
        assert_eq!(cmd.command.as_ref(), "ls");
        assert_eq!(cmd.args.len(), 1);
    }

    #[test]
    fn test_mcp_request() {
        let req1 = MCPRequest::new("test.method", "{}");
        let req2 = MCPRequest::new("test.method", "{}");
        assert_ne!(req1.request_id, req2.request_id);
    }

    #[test]
    fn test_delegated_task() {
        let task = DelegatedTask::new("agent1", "test prompt");
        assert_eq!(task.agent_id.as_ref(), "agent1");
        assert_eq!(task.max_retries, 1);
    }

    #[test]
    fn test_tool_router() {
        let router = ToolRouter::new();
        assert!(router.route("nonexistent").is_none());
    }
}
