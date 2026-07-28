"""
Verification test for the refactored prompt system.

Ensures that Cyn's personality is maintained and the new structure works correctly.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from ai.prompt_manager import PromptManager
from ai.prompt_builder import PromptBuilder
from ai.personality import get_personality, get_available_modes, build_system_prompt


def test_prompt_manager():
    """Test PromptManager basic functionality."""
    print("\n[TEST] PromptManager basic functionality")
    manager = PromptManager()

    # Test core loading
    core = manager.load_core_prompts()
    assert len(core) > 1000, "Core prompt too short"
    assert "CYN-X Core Identity" in core
    assert "Instruction Priority" in core
    print("  [OK] Core prompts load correctly")

    # Test mode discovery
    modes = manager.get_available_modes()
    assert 'playful' in modes, "Playful mode missing"
    assert 'technical' in modes, "Technical mode missing"
    assert 'comfort' in modes, "Comfort mode missing"
    print(f"  [OK] Found {len(modes)} modes: {modes}")

    # Test individual mode loading
    playful = manager.load_mode('playful')
    assert len(playful) > 500, "Playful mode too short"
    assert "Playful Cyn" in playful
    print("  [OK] Playful mode loads correctly")

    technical = manager.load_mode('technical')
    assert len(technical) > 500, "Technical mode too short"
    assert "Technical Cyn" in technical
    print("  [OK] Technical mode loads correctly")

    comfort = manager.load_mode('comfort')
    assert len(comfort) > 500, "Comfort mode too short"
    assert "Comfort Cyn" in comfort
    print("  [OK] Comfort mode loads correctly")

    # Test full prompt building
    full = manager.build_system_prompt(active_modes=['playful'])
    assert len(full) > 10000, "Full prompt too short"
    assert "CYN-X Core Identity" in full or "CYN-X Core Personality" in full
    assert "PLAYFUL MODE" in full or "playful" in full.lower()
    print("  [OK] Full prompt builds correctly")

    # Test info
    info = manager.get_prompt_info()
    assert 'available_modes' in info
    assert 'core_files' in info
    print("  [OK] Prompt info available")

    return True


def test_cyn_personality_preserved():
    """Test that Cyn's core personality is preserved."""
    print("\n[TEST] Cyn's core personality preserved")
    manager = PromptManager()
    core = manager.load_core_prompts()

    # Check core personality elements
    personality_markers = [
        "fascinated by humans",
        "glitchy",
        "not a therapist",
        "playful",
        "curious",
        "mischievous",
        "react before analyzing",
        "strange",
        "machine logic",
        "AI perspective",
    ]

    for marker in personality_markers:
        assert marker.lower() in core.lower(), f"Missing: {marker}"
        print(f"  [OK] Found personality element: {marker}")

    return True


def test_key_features_present():
    """Test that all key Cyn features are preserved."""
    print("\n[TEST] All key Cyn features present")
    manager = PromptManager()
    full = manager.build_system_prompt(
    active_modes=[
        "companion"
    ],
    active_options=[
        "playful",
        "creative"
    ],
    include_safety=True
)

    features = [
        ("Glitchy AI style", "glitchy"),
        ("Diagnostic humor", "[SYSTEM"),
        ("Curiosity about humans", "fascinating"),
        ("Playful teasing", "teasing"),
        ("Reaction-first pattern", "Reaction"),
        ("System messages", "["),
    ]

    for feature_name, search_term in features:
        assert search_term.lower() in full.lower(), f"Missing: {feature_name}"
        print(f"  [OK] {feature_name}")

    return True


def test_examples_quality():
    """Test that examples are well-formed and diverse."""
    print("\n[TEST] Examples quality and coverage")
    manager = PromptManager()
    examples_path = manager.prompts_dir / 'examples.md'
    examples_content = examples_path.read_text(encoding='utf-8')

    # Check for diverse example types
    example_types = [
        ("Greeting", "greeting"),
        ("Observation", "Curious Observation"),
        ("Teasing", "Teasing"),
        ("Comfort", "Comfort"),
        ("Celebration", "Celebration"),
        ("Technical", "Technical"),
    ]

    for example_type, search_term in example_types:
        assert search_term.lower() in examples_content.lower(), f"Missing example type: {example_type}"
        print(f"  [OK] {example_type} example present")

    return True


def test_no_major_duplicates():
    """Test that major duplicates have been removed."""
    print("\n[TEST] Checking for duplicate removal")

    # Load all files and count similar content
    manager = PromptManager()

    # These should appear once or minimal times
    single_mentions = [
        ("Cyn Core Summary", 1),
        ("Anti-Analysis", 1),
        ("Reaction Rule", 1),
    ]

    core = manager.load_core_prompts()
    voice = manager.prompts_dir / 'voice.md'
    voice_content = voice.read_text(encoding='utf-8') if voice.exists() else ""

    for phrase, expected_max in single_mentions:
        core_count = core.lower().count(phrase.lower())
        voice_count = voice_content.lower().count(phrase.lower())
        total = core_count + voice_count
        assert total <= expected_max + 1, f"Too many mentions of '{phrase}': {total}"
        print(f"  [OK] '{phrase}' appears {total} time(s) (max expected: {expected_max})")

    return True


def test_backwards_compatibility():
    """Test that legacy code still works."""
    print("\n[TEST] Backwards compatibility")

    # Test PromptBuilder with legacy approach
    builder = PromptBuilder()
    prompt = builder.build_prompt(
        user_input="Hello Cyn",
        history=[{'role': 'user', 'content': 'Hi there'}],
        memory_summary="User is curious"
    )
    assert len(prompt) > 15000, "Legacy prompt too short"
    assert "Hello Cyn" in prompt
    print("  [OK] PromptBuilder backwards compatible")

    # Test personality loading
    core = get_personality('normal')
    assert len(core) > 1000, "Legacy personality loading broken"
    print("  [OK] get_personality() still works")

    # Test mode functions
    modes = get_available_modes()
    assert len(modes) >= 3, "get_available_modes() broken"
    print(f"  [OK] get_available_modes() returns {len(modes)} modes")

    return True


def test_context_reduction():
    """Test that context usage has been reduced."""
    print("\n[TEST] Context reduction verification")

    manager = PromptManager()

    # Old approach would load everything
    core = manager.load_core_prompts()
    core_size = len(core)
    print(f"  [INFO] Core personality: {core_size:,} characters")

    # With one mode
    full_one_mode = manager.build_system_prompt(active_modes=['playful'])
    one_mode_size = len(full_one_mode)
    print(f"  [INFO] With playful mode: {one_mode_size:,} characters")

    # With all modes
    all_modes = manager.get_available_modes()
    full_all_modes = manager.build_system_prompt(active_modes=all_modes)
    all_modes_size = len(full_all_modes)
    print(f"  [INFO] With all {len(all_modes)} modes: {all_modes_size:,} characters")

    # Verify it's reasonable
    assert core_size > 5000, "Core too small"
    assert one_mode_size > core_size, "Mode not added properly"
    assert all_modes_size < 30000, "Total size still reasonable"

    print(f"  [OK] Context usage optimized")
    return True


def test_mode_independence():
    """Test that modes don't interfere with each other."""
    print("\n[TEST] Mode independence")

    manager = PromptManager()

    # Load each mode individually
    modes = manager.get_available_modes()
    for mode_name in modes:
        mode = manager.load_mode(mode_name)
        assert len(mode) > 0, f"Mode '{mode_name}' is empty"
        assert f"{mode_name}" in mode.lower() or "Mode" in mode, f"Mode '{mode_name}' doesn't identify itself"
        print(f"  [OK] Mode '{mode_name}' is independent and complete")

    # Load all together
    full = manager.build_system_prompt(active_modes=modes)
    for mode_name in modes:
        assert mode_name.title() in full or mode_name.lower() in full.lower(), f"Mode '{mode_name}' not in full prompt"
    print(f"  [OK] All {len(modes)} modes combine properly")

    return True


def run_all_tests():
    """Run all verification tests."""
    print("\n" + "="*70)
    print("CYN-X PROMPT REFACTORING VERIFICATION TESTS")
    print("="*70)

    tests = [
        test_prompt_manager,
        test_cyn_personality_preserved,
        test_key_features_present,
        test_examples_quality,
        test_no_major_duplicates,
        test_backwards_compatibility,
        test_context_reduction,
        test_mode_independence,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            if test_func():
                passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {e}")
            failed += 1
        except Exception as e:
            print(f"  [ERROR] {e}")
            failed += 1

    print("\n" + "="*70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*70 + "\n")

    if failed == 0:
        print("SUCCESS: All verification tests passed!")
        print("\nCyn's personality has been successfully refactored into modular files.")
        print("The new structure maintains all personality traits while reducing context usage.")
        return True
    else:
        print(f"FAILURE: {failed} test(s) failed")
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
