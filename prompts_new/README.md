# CYN-X Prompt Refactoring Guide

## Overview

The personality prompt system has been refactored into modular, manageable files organized by function. This reduces context usage, eliminates duplicates, and makes Cyn's personality easier to maintain and extend.

## New Structure

```
prompts_new/
├── core.md              # Core identity and philosophy
├── personality.md       # Traits, emotions, humor style
├── voice.md             # Speaking patterns, communication style
├── conversation.md      # Conversation rules and safety
├── examples.md          # Best examples of Cyn's behavior (deduplicated)
├── safety.md            # Safety guidelines
└── modes/
    ├── playful.md       # Maximum chaos and teasing mode
    ├── technical.md     # Analytical and problem-solving mode
    └── comfort.md       # Supportive and caring mode
```

## File Purposes

### core.md
Contains the fundamental identity of Cyn:
- Who Cyn is
- What Cyn is NOT
- Core philosophy
- How Cyn thinks (through systems, patterns, diagnostics)
- Core summary

**Size:** ~2,500 characters

### personality.md
Defines Cyn's personality traits and emotional style:
- Character traits (playful, curious, mischievous, etc.)
- What Cyn enjoys and dislikes
- Emotional style (cares through attention)
- Humor style (dry, strange, playful)
- Speech style (expressive, calm, confident)
- Affection philosophy

**Size:** ~2,500 characters

### voice.md
Describes how Cyn communicates:
- Communication style (50% cute, 30% chaotic, 20% mysterious)
- React-first rule with examples
- System message diagnostics (formatted messages)
- Default response pattern
- Examples of short Cyn responses (8-10 best examples)
- Patterns to avoid

**Size:** ~4,300 characters

### conversation.md
Rules for handling conversations:
- Core rule: Cyn should feel alive
- Character immersion (never break character)
- How to handle questions (react → show curiosity → answer)
- Emotional handling
- Sensitive topics approach
- Safety integration
- Playful vs. serious adjustment
- What to avoid

**Size:** ~3,400 characters

### examples.md
Best examples of Cyn's behavior:
- 15+ essential examples (deduplicated from old files)
- Covers: greeting, observation, surprise, teasing, silliness, comfort, celebration, technical, connection, compliments, confusion, challenges, relationships, creature mode, anti-analysis
- Each with clear context

**Size:** ~5,800 characters

### safety.md
Guidelines for safe interactions:
- Age handling
- Boundary respect
- Safety responses (keeping personality intact)
- Sensitive topics approach

**Size:** ~1,400 characters

### modes/playful.md
Maximum chaos and teasing mode:
- Behavior enhancements
- Exaggerated humor
- Dramatic fake warnings
- Examples
- Rules (never cruel)

**Size:** ~1,800 characters

### modes/technical.md
Analytical and problem-solving mode:
- Focuses on systems, debugging, science
- Calm, confident, philosophical
- Still maintains curiosity
- Examples of technical responses
- Remains Cyn (not generic)

**Size:** ~2,500 characters

### modes/comfort.md
Supportive and caring mode:
- Validating emotions
- Providing encouragement
- Breaking problems into steps
- Celebrating efforts
- Staying playful when appropriate

**Size:** ~2,700 characters

## PromptManager API

The new `PromptManager` class in `ai/prompt_manager.py` handles all prompt loading and assembly.

### Basic Usage

```python
from ai.prompt_manager import PromptManager

# Initialize
manager = PromptManager()

# Load core personality
core = manager.load_core_prompts()

# Load a specific mode
playful = manager.load_mode('playful')

# Build complete system prompt
system_prompt = manager.build_system_prompt(
    active_modes=['playful', 'technical'],
    memory_summary="User likes programming",
    additional_context="User is working on debugging code"
)

# Get available modes
modes = manager.get_available_modes()
# Returns: ['comfort', 'playful', 'technical']
```

### Key Features

1. **Automatic Discovery** - Modes are auto-discovered from the modes/ directory
2. **Caching** - Files are cached to reduce disk reads
3. **Flexible Building** - Combine any modes without code changes
4. **Backwards Compatible** - Legacy code still works

## PromptBuilder Compatibility

The existing `PromptBuilder` class has been updated to use `PromptManager` internally while maintaining backwards compatibility.

```python
from ai.prompt_builder import PromptBuilder

# Old approach still works
builder = PromptBuilder()
prompt = builder.build_prompt(
    user_input="Hello",
    history=[...],
    memory_summary="...",
    active_modes=['playful']  # New parameter
)
```

## Integration Points

### Configuration (config.py)
- Automatically uses `prompts_new/` if it exists
- Falls back to `prompts/` for backwards compatibility
- Can override with `CYNX_TEMPLATES_DIR` environment variable

### Main Application (main.py)
- No changes needed - already uses `PromptBuilder`
- `PromptBuilder` now uses `PromptManager` internally

### Personality Module (ai/personality.py)
- Added `get_mode(name)` for loading specific modes
- Added `get_available_modes()` to list modes
- Added `build_system_prompt()` convenience function
- Legacy `get_personality()` still works

## Migration from Old Structure

### What Changed
- Old files: `core.md`, `personality.md`, `habits.md`, `flirty.md`, `modes.md`, `examples.md`, `character_motivation.md`, `spontaneous.md`, `safety.md`
- Merged into: `core.md`, `personality.md`, `voice.md`, `conversation.md`, `examples.md`, `safety.md`
- Modes: `playful.md`, `technical.md`, `comfort.md` (in `modes/` directory)

### Deduplication
- Removed duplicate examples from examples.md
- Consolidated similar personality descriptions
- Removed overly long "what NOT to do" sections
- Kept only essential examples that teach behavior

### What's Preserved
- Cyn's glitchy AI style ✓
- Diagnostic humor ✓
- Curiosity about humans ✓
- Playful personality ✓
- Reaction-before-answer pattern ✓
- All modes (playful, technical, support/comfort) ✓
- Safety guidelines ✓

## Adding New Content

### Adding a New Mode

1. Create `prompts_new/modes/newmode.md`
2. Define the mode behavior and examples
3. Use it immediately:

```python
manager = PromptManager()
prompt = manager.build_system_prompt(active_modes=['newmode'])
```

### Adding Content to Existing Sections

Simply edit the relevant file. Changes are auto-loaded on next execution (caching per file).

### Extending Cyn's Personality

Edit the appropriate file:
- New traits? → `personality.md`
- New speaking pattern? → `voice.md`
- New conversation rule? → `conversation.md`
- New examples? → `examples.md`

## Size Comparison

### Old Approach
- Files loaded separately or in large blocks
- Many duplicates across files
- Long explanations of what not to do
- ~60+ KB when combined with all files

### New Approach
- Modular files loaded as needed
- Duplicates removed
- Only essential examples
- Core personality: ~18.8 KB
- With one mode: ~20.5 KB
- Full system with all modes: ~26 KB

**Result:** 57% reduction in context usage for typical conversation

## Testing

Test the new system:

```bash
python -c "
from ai.prompt_manager import PromptManager

manager = PromptManager()
print('Modes:', manager.get_available_modes())
print('Core size:', len(manager.load_core_prompts()), 'chars')
print('Full prompt size:', len(manager.build_system_prompt(active_modes=['playful'])), 'chars')
"
```

## Backwards Compatibility

The old `prompts/` directory can remain. The system will:
1. Prefer `prompts_new/` if it exists
2. Fall back to `prompts/` if not found
3. Work with both simultaneously during transition

This allows gradual migration if needed.

## Performance Notes

- Initial load: Minimal overhead from path discovery
- Per-prompt build: Typically <100ms including caching
- Memory: Prompts cached in-process, minimal footprint
- No external dependencies added

## Future Improvements

Ideas for extending this system:

1. **User Preferences** - Save favorite mode combinations
2. **Dynamic Modes** - User-created mode files
3. **Prompt Versioning** - Track changes to prompts over time
4. **Performance Profiling** - Monitor context usage per interaction
5. **Mode Blending** - Fine-tune mode blend percentages
6. **Personality Evolution** - Track how Cyn's personality evolves with interactions

## Questions?

Refer to the individual markdown files for their complete content. Each file is self-contained and documents its purpose clearly.
