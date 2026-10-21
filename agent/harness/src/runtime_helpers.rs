/// Ultra-fast agent runtime helpers
use std::sync::Arc;
use std::sync::atomic::{AtomicU32, Ordering};

#[derive(Clone, Debug)]
pub struct ExecutionContext {
    pub tool_name: Arc<str>,
    pub tool_input: Arc<str>,
    pub agent_id: Arc<str>,
    pub step: u32,
}

impl ExecutionContext {
    pub fn new(tool_name: impl Into<String>, tool_input: impl Into<String>, agent_id: impl Into<String>) -> Self {
        ExecutionContext {
            tool_name: Arc::from(tool_name.into()),
            tool_input: Arc::from(tool_input.into()),
            agent_id: Arc::from(agent_id.into()),
            step: 0,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum HookType {
    ToolPre = 0,
    ToolPost = 1,
    ToolError = 2,
    Decision = 3,
    Autonomy = 4,
}

pub struct RuntimeHelper {
    hook_count: Arc<AtomicU32>,
    autonomy_decisions: Arc<AtomicU32>,
}

impl RuntimeHelper {
    pub fn new() -> Self {
        RuntimeHelper {
            hook_count: Arc::new(AtomicU32::new(0)),
            autonomy_decisions: Arc::new(AtomicU32::new(0)),
        }
    }

    pub fn register_hook(&self, _hook_type: HookType, _name: impl Into<String>) {
        self.hook_count.fetch_add(1, Ordering::Relaxed);
    }

    pub fn execute_hooks(&self, _hook_type: HookType, _ctx: &ExecutionContext) -> bool {
        self.hook_count.load(Ordering::Relaxed) > 0
    }

    pub fn record_autonomy(&self) {
        self.autonomy_decisions.fetch_add(1, Ordering::Relaxed);
    }

    pub fn get_autonomy_count(&self) -> u32 {
        self.autonomy_decisions.load(Ordering::Relaxed)
    }

    pub fn is_autonomous(&self, ctx: &ExecutionContext) -> bool {
        !ctx.tool_input.is_empty() && !ctx.tool_input.starts_with("user:")
    }
}

impl Clone for RuntimeHelper {
    fn clone(&self) -> Self {
        RuntimeHelper {
            hook_count: Arc::clone(&self.hook_count),
            autonomy_decisions: Arc::clone(&self.autonomy_decisions),
        }
    }
}

#[derive(Clone, Debug)]
pub struct ToolResult {
    pub tool_name: Arc<str>,
    pub success: bool,
    pub output: Arc<str>,
    pub error: Option<Arc<str>>,
}

impl ToolResult {
    pub fn success(tool_name: impl Into<String>, output: impl Into<String>) -> Self {
        ToolResult {
            tool_name: Arc::from(tool_name.into()),
            success: true,
            output: Arc::from(output.into()),
            error: None,
        }
    }

    pub fn error(tool_name: impl Into<String>, error: impl Into<String>) -> Self {
        ToolResult {
            tool_name: Arc::from(tool_name.into()),
            success: false,
            output: Arc::from(""),
            error: Some(Arc::from(error.into())),
        }
    }
}

#[derive(Clone, Debug)]
pub struct RuntimeState {
    pub total_tools_executed: u32,
    pub total_autonomy_decisions: u32,
    pub total_errors: u32,
    pub last_tool: Option<Arc<str>>,
}

impl RuntimeState {
    pub fn new() -> Self {
        RuntimeState {
            total_tools_executed: 0,
            total_autonomy_decisions: 0,
            total_errors: 0,
            last_tool: None,
        }
    }

    pub fn record_execution(&mut self, tool_name: &str) {
        self.total_tools_executed += 1;
        self.last_tool = Some(Arc::from(tool_name));
    }

    pub fn record_error(&mut self) {
        self.total_errors += 1;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_execution_context() {
        let ctx = ExecutionContext::new("test", "input", "agent");
        assert_eq!(ctx.tool_name.as_ref(), "test");
    }

    #[test]
    fn test_autonomy() {
        let helper = RuntimeHelper::new();
        assert_eq!(helper.get_autonomy_count(), 0);
        helper.record_autonomy();
        assert_eq!(helper.get_autonomy_count(), 1);
    }

    #[test]
    fn test_tool_result() {
        let r = ToolResult::success("tool", "output");
        assert!(r.success);
    }
}
