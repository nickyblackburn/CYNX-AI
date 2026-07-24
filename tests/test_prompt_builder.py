from ai.prompt_builder import PromptBuilder


def test_build_prompt_minimal():
    pb = PromptBuilder(templates_dir='prompts')
    p = pb.build_prompt('Hello', mode_fragment='modefrag', personality_fragment='persfrag')
    assert 'Hello' in p
    assert 'modefrag' in p
    assert 'persfrag' in p
