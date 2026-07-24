"""
ModeManager: holds mode specs and simple policy enforcement per-mode.
"""
from typing import Dict, List


class ModeSpec:
    def __init__(self, name: str, allowed_tools: List[str] = None, instruction_fragment: str = ''):
        self.name = name
        self.allowed_tools = allowed_tools or []
        self.instruction_fragment = instruction_fragment


class ModeManager:
    def __init__(self):
        self.modes: Dict[str, ModeSpec] = {}
        self._init_default_modes()

    def _init_default_modes(self):
        self.modes['normal'] = ModeSpec('normal', allowed_tools=['calculator', 'web_search', 'filesystem'], instruction_fragment='Be neutral and helpful.')
        self.modes['solver'] = ModeSpec('solver', allowed_tools=['calculator', 'web_search'], instruction_fragment='Be analytical and concise.')
        self.modes['gremlin'] = ModeSpec('gremlin', allowed_tools=['calculator'], instruction_fragment='Playful, but obey safety rules.')
        self.modes['helper'] = ModeSpec('helper', allowed_tools=['calculator','web_search','filesystem'], instruction_fragment='Be patient and explanatory.')
        self.modes['flirty'] = ModeSpec('flirty', allowed_tools=['calculator'], instruction_fragment='Playful but respectful; enforce safety.')

    def get_mode(self, name: str) -> ModeSpec:
        return self.modes.get(name, self.modes['normal'])

    def allowed_tools_for(self, name: str):
        return self.get_mode(name).allowed_tools
