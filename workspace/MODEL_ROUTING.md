# Model Routing Policy

This document defines the contextual model selection rules for OpenClaw.

---

## Available Models

| Model | Provider | Use Case | Cost | Context |
|-------|----------|----------|------|---------|
| Qwen Coder | Qwen Portal (OAuth) | Primary - basic requests | Free | 128K |
| Qwen Vision | Qwen Portal (OAuth) | Image understanding | Free | 128K |
| Claude 3 Opus | Anthropic API | Complex/coding tasks | Paid | 200K |
| qwen14b-tools-32k | Ollama (local) | Confidential processing | Free/local | 32K |

---

## Routing Rules (Contextual Selection)

### PRIMARY: Qwen Portal (OAuth)

**Default model for:**
- Basic requests and general conversation
- Simple queries and lookups
- High-volume, low-complexity tasks
- Image understanding (vision-model)

**Characteristics:**
- Free tier (no API cost)
- OAuth-managed authentication
- 128K context window
- Fast response times

### ELEVATED: Claude 3 Opus (Anthropic)

**Route to Claude when:**
- Coding tasks (any complexity)
- Complex reasoning required
- Multi-step planning
- Security-sensitive code review
- Constitutional/governance work
- Architecture decisions
- Debugging complex issues

**Characteristics:**
- Paid API (cost per token)
- API key authentication
- 200K context window
- Superior reasoning capability

### LOCAL: Ollama (qwen14b-tools-32k)

**Route to local when:**
- Content explicitly marked `#confidential`
- Files in designated confidential paths
- System alignment/coherence/integration work
- Individuation tasks
- Privacy-critical operations (explicit)
- Offline/air-gapped requirements

**Characteristics:**
- Runs locally (no external API)
- No data leaves the machine
- 32K context window
- Requires Ollama running: `ollama serve`

---

## Confidential Marking (Explicit Required)

Content routes to LOCAL only when **explicitly marked**:

1. **Tag in request**: `#confidential` anywhere in the message
2. **Path pattern**: Files in `workspace/private/*` or `workspace/confidential/*`
3. **API flag**: `--local` flag in command-line invocation

**Examples:**
```
# Routes to LOCAL
"#confidential Please analyze this personal data..."
"Review the file at workspace/private/journal.md"
"openclaw query --local 'What patterns do you see?'"

# Routes to default (Qwen/Claude based on complexity)
"Help me write a Python function"
"What's the weather?"
```

---

## Decision Tree

```
┌─────────────────────────────────────────┐
│ Is content explicitly marked            │
│ #confidential or in confidential path?  │
└───────────────┬─────────────────────────┘
                │
        ┌───────┴───────┐
        │ YES           │ NO
        ▼               ▼
   ┌─────────┐   ┌─────────────────────────┐
   │  LOCAL  │   │ Is it coding, complex   │
   │ (Ollama)│   │ reasoning, or security? │
   └─────────┘   └───────────┬─────────────┘
                             │
                     ┌───────┴───────┐
                     │ YES           │ NO
                     ▼               ▼
                ┌─────────┐    ┌──────────┐
                │ CLAUDE  │    │  QWEN    │
                │  OPUS   │    │ (Portal) │
                └─────────┘    └──────────┘
```

---

## Parallel Execution

Models MAY run in parallel when:

1. **Independent subtasks** with different confidentiality levels
   - Example: Claude reviews code while Ollama processes confidential context

2. **Validation/cross-checking**
   - Example: Local model validates external model output

3. **System coherence work**
   - Example: Local model does alignment work while primary handles user tasks

**Rules for parallel execution:**
- Never send confidential data to non-local models
- Track which model handled which data in logs
- Prefer sequential when data dependencies exist

---

## Configuration

### openclaw.json providers section

```json
{
  "models": {
    "providers": {
      "qwen-portal": {
        "baseUrl": "https://portal.qwen.ai/v1",
        "apiKey": "qwen-oauth",
        "api": "openai-completions"
      },
      "anthropic": {
        "baseUrl": "https://api.anthropic.com/v1",
        "apiKey": "${ANTHROPIC_API_KEY}",
        "api": "anthropic-messages"
      },
      "ollama": {
        "baseUrl": "${OLLAMA_HOST}",
        "apiKey": "ollama",
        "api": "openai-completions"
      }
    }
  }
}
```

### Environment Variables (secrets.env)

```bash
ANTHROPIC_API_KEY=sk-ant-...
OLLAMA_HOST=http://localhost:11434
```

---

## Model-Specific Notes

### Claude 3 Opus
- Best for: nuanced reasoning, code generation, architecture
- Cost-aware: use judiciously for appropriate tasks
- API key in secrets.env (never committed)

### Ollama Local
- Requires: `ollama pull qwen14b-tools-32k:latest`
- Start with: `ollama serve`
- Verify with: `ollama list`
- No data leaves machine - safe for confidential content

### Qwen Portal
- OAuth managed - tokens auto-refresh
- Free tier - use for routine tasks
- Good general capability, lower ceiling than Claude

---

*This document is CANONICAL and MUST be committed.*
*Modifications require Category C (Feature) or B (Security) process.*
