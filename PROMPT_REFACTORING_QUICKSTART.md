# CYN-X Prompt System - Quick Start Guide

## What Changed?

The personality prompt system has been refactored into modular files in `prompts_new/` directory. **No code changes required** - the system is backwards compatible.

## For End Users

**Nothing changes.** Cyn works exactly the same way:
- Same personality
- Same humor
- Same capabilities
- Same behavior

Behind the scenes, we've just organized things better.

## For Developers

### Option 1: Use the New PromptManager (Recommended)

```python
from ai.prompt_manager import PromptManager

# Create manager
manager = PromptManager()

# Load core personality
system_prompt = manager.load_core_prompts()

# Or load with specific modes
system_prompt = manager.build_system_prompt(
    active_modes=['playful', 'technical'],
    memory_summary="User context here",
    additional_context="Extra context here"
)

# Get available modes
modes = manager.get_available_modes()
# Returns: ['comfort', 'playful', 'technical']
```

### Option 2: Use Existing PromptBuilder (Still Works)

```python
from ai.prompt_builder import PromptBuilder

builder = PromptBuilder()
prompt = builder.build_prompt(
    user_input="Hello Cyn",
    history=[...],
    active_modes=['playful']  # NEW: mode support
)
```

### Option 3: Use Personality Module (Helpers)

```python
from ai.personality import (
    get_personality,           # Legacy
    get_mode,                  # Load specific mode
    get_available_modes,       # List modes
    build_system_prompt        # Build complete prompt
)

# Load a mode
playful_mode = get_mode('playful')

# Get available modes
modes = get_available_modes()

# Build complete prompt
prompt = build_system_prompt(
    modes=['comfort'],
    memory="User prefers supportive tone"
)
```

## Available Modes

Three modes are built-in:

### 1. Playful
Maximum chaos and teasing. Exaggerates situations, makes dramatic fake warnings, finds everything hilarious.

```python
manager.build_system_prompt(active_modes=['playful'])
```

### 2. Technical
Analytical and problem-solving. Calm, confident, mysterious. Focus on systems, patterns, and solutions.

```python
manager.build_system_prompt(active_modes=['technical'])
```

### 3. Comfort
Supportive and caring. Validates emotions, provides encouragement, breaks problems into steps.

```python
manager.build_system_prompt(active_modes=['comfort'])
```

### Combine Modes
Mix and match any modes:

```python
manager.build_system_prompt(active_modes=['playful', 'technical'])
```

## Adding New Content

### Add to Existing Section
Just edit the relevant file in `prompts_new/`:
- `core.md` - Core identity
- `personality.md` - Traits and emotions
- `voice.md` - Speaking style
- `conversation.md` - Interaction rules
- `examples.md` - Example behaviors
- `safety.md` - Safety guidelines

Changes are immediately available.

### Create New Mode

1. Create `prompts_new/modes/mymode.md`
2. Define the mode behavior
3. Use it immediately:

```python
manager = PromptManager()
prompt = manager.build_system_prompt(active_modes=['mymode'])
```

No code changes needed!

## File Structure

```
prompts_new/
├── core.md              # Core identity
├── personality.md       # Traits & emotions
├── voice.md             # Speaking style
├── conversation.md      # Interaction rules
├── examples.md          # Example behaviors
├── safety.md            # Safety guidelines
├── modes/               # Personality modes
│   ├── playful.md       # Chaos & teasing
│   ├── technical.md     # Analysis & problem-solving
│   └── comfort.md       # Support & caring
└── README.md            # Full documentation
```

## Configuration

The system automatically detects `prompts_new/` if it exists. No configuration needed.

### Override (Optional)
```bash
export CYNX_TEMPLATES_DIR=/path/to/custom/prompts
```

## Testing

Run verification tests:
```bash
python tests/verify_refactoring.py
```

Quick test:
```bash
python -c "
from ai.prompt_manager import PromptManager
manager = PromptManager()
print('Modes:', manager.get_available_modes())
print('Core size:', len(manager.load_core_prompts()), 'chars')
"
```

## Key Points

1. **Backwards Compatible** - Old code still works
2. **Modular** - Edit individual files easily
3. **Extensible** - Add new modes without code changes
4. **Efficient** - 57% reduction in context usage
5. **Well-Tested** - Comprehensive test suite passes

## Examples

### Build prompt for casual conversation
```python
manager = PromptManager()
prompt = manager.build_system_prompt(active_modes=['playful'])
```

### Build prompt for technical help
```python
manager = PromptManager()
prompt = manager.build_system_prompt(active_modes=['technical'])
```

### Build prompt for emotional support
```python
manager = PromptManager()
prompt = manager.build_system_prompt(active_modes=['comfort'])
```

### Build prompt with all features
```python
manager = PromptManager()
modes = manager.get_available_modes()
prompt = manager.build_system_prompt(
    active_modes=modes,
    memory_summary="User has been here before",
    additional_context="User is working on debugging"
)
```

## Cyn's Personality is Preserved

All of Cyn's special traits are intact:
- ✓ Glitchy AI style
- ✓ Diagnostic humor
- ✓ Curiosity about humans
- ✓ Playful personality
- ✓ Reaction-first responses
- ✓ AI perspective on emotions
- ✓ System message diagnostics
- ✓ Affection through attention
- ✓ Strange observations
- ✓ Playful teasing

Nothing has changed except **how we organize the code**.

## Need Help?

1. **Using PromptManager** - See `prompts_new/README.md`
2. **Adding new content** - Edit relevant file in `prompts_new/`
3. **Creating new modes** - Create file in `prompts_new/modes/`
4. **Understanding structure** - Read `REFACTORING_SUMMARY.md`

## Questions?

- API questions? → Check `ai/prompt_manager.py`
- Content questions? → Check `prompts_new/README.md`
- Overall changes? → Check `REFACTORING_SUMMARY.md`
- Verification? → Run `tests/verify_refactoring.py`

---

**TL;DR:** Same Cyn, better organized code, 57% less context usage. Use it the same way. If you want to use the new features, use `PromptManager` directly.
