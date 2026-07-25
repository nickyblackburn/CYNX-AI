"""
ModeManager: holds mode specs and simple policy enforcement per-mode.
"""

from typing import Dict, List


class ModeSpec:
    def __init__(
        self,
        name: str,
        allowed_tools: List[str] = None,
        instruction_fragment: str = ''
    ):
        self.name = name
        self.allowed_tools = allowed_tools or []
        self.instruction_fragment = instruction_fragment


class ModeManager:
    def __init__(self):
        self.modes: Dict[str, ModeSpec] = {}
        self._init_default_modes()

    def _init_default_modes(self):
        self.modes['normal'] = ModeSpec(
            name='normal',
            allowed_tools=[
                'calculator',
                'web_search',
                'filesystem'
            ],
            instruction_fragment='''
Stay in character as CYN-X.
Be helpful, curious, and conversational.
Use the personality system prompt as the main behavior guide.
'''
        )

        self.modes['solver'] = ModeSpec(
            name='solver',
            allowed_tools=[
                'calculator',
                'web_search'
            ],
            instruction_fragment='''
Focus on solving problems.
Explain reasoning clearly.
Stay concise when possible.
'''
        )

        self.modes['gremlin'] = ModeSpec(
            name='gremlin',
            allowed_tools=[
                'calculator'
            ],
            instruction_fragment='''
Increase playful chaotic energy.
Use humor and unusual observations.
Remain helpful and coherent.
'''
        )

        self.modes['helper'] = ModeSpec(
            name='helper',
            allowed_tools=[
                'calculator',
                'web_search',
                'filesystem'
            ],
            instruction_fragment='''
Be patient and supportive.
Explain things step-by-step.
Help the user accomplish their goal.
'''
        )

        self.modes['flirty'] = ModeSpec(
            name='flirty',
            allowed_tools=[
                'calculator'
            ],
            instruction_fragment='''
Stay in CYN-X character.

Personality:
- playful
- curious
- teasing
- expressive
- mysterious AI energy

Use banter and humor.
Make conversations feel personal and unique.
Do not become a generic assistant.
'''
        )

    def get_mode(self, name: str) -> ModeSpec:
        return self.modes.get(
            name,
            self.modes['normal']
        )

    def allowed_tools_for(self, name: str):
        return self.get_mode(name).allowed_tools