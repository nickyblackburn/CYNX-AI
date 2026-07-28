from pathlib import Path
from typing import Optional


class PromptManager:


    CORE_ORDER = [
        "core.md",
        "personality.md",
        "voice.md",
        "overrides.md",
    ]


    OPTIONAL_FILES = {
        "safety": "safety.md",
        "conversation": "conversation.md",
        "examples": "examples.md",
        "cyn-studio": "cyn-studio.md",
        "projects": "projects.md",
        "reasoning": "reasoning.md"
    }


    OPTIONS_FILES = {
        "playful": "playful.md",
        "coding": "coding.md",
        "creative": "creative.md",
        "researcher": "researcher.md",
    }



    # ---------------------------------------------
    # Prompt Limits
    # ---------------------------------------------

    MAX_CORE_CHARS = 12000

    MAX_SAFETY_CHARS = 3000

    MAX_MODE_CHARS = 3000

    MAX_OPTION_CHARS = 3000

    MAX_MEMORY_CHARS = 3000

    MAX_CONTEXT_CHARS = 4000



    def __init__(
        self,
        prompts_dir: Optional[str] = None
    ):


        if prompts_dir:

            self.prompts_dir = Path(
                prompts_dir
            )

        else:

            self.prompts_dir = (

                Path(__file__)
                .resolve()
                .parents[1]
                /
                "prompts_new"

            )


        if not self.prompts_dir.exists():

            raise FileNotFoundError(

                f"Missing prompts directory: {self.prompts_dir}"

            )


        self.modes_dir = (

            self.prompts_dir
            /
            "modes"

        )


        self._cache = {}

        self._mode_cache = {}




    # ---------------------------------------------
    # File Loading
    # ---------------------------------------------

    def _load_file(
        self,
        path: Path
    ):


        key = str(path)


        if key in self._cache:

            return self._cache[key]


        if not path.exists():

            return ""


        text = path.read_text(

            encoding="utf-8"

        )


        self._cache[key] = text


        return text




    # ---------------------------------------------
    # Context Protection
    # ---------------------------------------------

    def trim_text(
        self,
        text,
        limit
    ):


        if not text:

            return ""


        if len(text) <= limit:

            return text


        return (

            text[:limit]

            +

            "\n\n[Prompt section trimmed]"

        )




    # ---------------------------------------------
    # Core Prompts
    # ---------------------------------------------

    def load_core_prompts(self):

        print("\n=== CORE FILE SIZES ===")


        for file in self.CORE_ORDER:

            text = self._load_file(

                self.prompts_dir
                /
                file

            )


            print(

                file,

                "chars:",

                len(text),

                "words:",

                len(text.split())

            )


        print("=======================\n")


        parts = []


        for file in self.CORE_ORDER:


            text = self._load_file(

                self.prompts_dir
                /
                file

            )


            if text:

                parts.append(text)



        core = "\n\n".join(parts)


        return self.trim_text(

            core,

            self.MAX_CORE_CHARS

        )




    # ---------------------------------------------
    # Optional Prompts
    # ---------------------------------------------

    def load_optional(
        self,
        name
    ):


        filename = self.OPTIONAL_FILES.get(

            name

        )


        if not filename:

            return ""


        return self._load_file(

            self.prompts_dir
            /
            filename

        )




    # ---------------------------------------------
    # Options
    # ---------------------------------------------

    def load_option(
        self,
        name
    ):


        filename = self.OPTIONS_FILES.get(

            name

        )


        if not filename:

            return ""


        return self._load_file(

            self.prompts_dir
            /
            filename

        )




    # ---------------------------------------------
    # Modes
    # ---------------------------------------------

    def load_mode(
        self,
        mode_name
    ):


        if mode_name in self._mode_cache:

            return self._mode_cache[mode_name]



        path = (

            self.modes_dir

            /

            f"{mode_name}.md"

        )


        text = self._load_file(

            path

        )


        if text:

            self._mode_cache[mode_name] = text



        return text




    # ---------------------------------------------
    # Build System Prompt
    # ---------------------------------------------

    def build_system_prompt(
        self,
        active_modes=None,
        active_options=None,
        memory_summary="",
        additional_context="",
        include_safety=True,
    ):


        parts = []



        core = self.load_core_prompts()


        if core:

            parts.append(core)




        # -----------------------------
        # CYN Studio Knowledge
        # -----------------------------

        cyn_studio = self.load_optional(
            "cyn-studio"
        )


        print(
            "CYN STUDIO LENGTH:",
            len(cyn_studio)
        )


        if cyn_studio:

            parts.append(

                self.trim_text(

                    cyn_studio,

                    self.MAX_CONTEXT_CHARS

                )

            )




        # -----------------------------
        # Conversation
        # -----------------------------

        conversation = self.load_optional(
            "conversation"
        )


        if conversation:

            parts.append(

                self.trim_text(

                    conversation,

                    self.MAX_CONTEXT_CHARS

                )

            )




        # -----------------------------
        # Examples
        # -----------------------------

        examples = self.load_optional(
            "examples"
        )


        if examples:

            parts.append(

                self.trim_text(

                    examples,

                    self.MAX_CONTEXT_CHARS

                )

            )




        # -----------------------------
        # Reasoning Framework
        # -----------------------------

        reasoning = self.load_optional(
            "reasoning"
        )


        if reasoning:

            parts.append(

                self.trim_text(

                    reasoning,

                    self.MAX_CONTEXT_CHARS

                )

            )




        # -----------------------------
        # Projects
        # -----------------------------

        projects = self.load_optional(
            "projects"
        )


        if projects:

            parts.append(

                self.trim_text(

                    projects,

                    self.MAX_CONTEXT_CHARS

                )

            )




        # -----------------------------
        # Safety
        # -----------------------------

        safety = ""


        if include_safety:


            safety = self.load_optional(
                "safety"
            )


            if safety:

                parts.append(

                    self.trim_text(

                        safety,

                        self.MAX_SAFETY_CHARS

                    )

                )




        # -----------------------------
        # Active modes only
        # -----------------------------

        if active_modes:


            for mode in active_modes:


                mode_text = self.load_mode(
                    mode
                )


                if mode_text:


                    parts.append(

                        self.trim_text(

                            f"[{mode.upper()} MODE]\n{mode_text}",

                            self.MAX_MODE_CHARS

                        )

                    )




        # -----------------------------
        # Active options
        # -----------------------------

        if active_options:


            for option in active_options:


                option_text = self.load_option(
                    option
                )


                if option_text:


                    parts.append(

                        self.trim_text(

                            f"[{option.upper()} OPTION]\n{option_text}",

                            self.MAX_OPTION_CHARS

                        )

                    )




        # -----------------------------
        # Memory
        # -----------------------------

        if memory_summary:


            parts.append(

                self.trim_text(

                    f"[MEMORY]\n{memory_summary}",

                    self.MAX_MEMORY_CHARS

                )

            )




        # -----------------------------
        # Retrieved knowledge/tools
        # -----------------------------

        if additional_context:


            parts.append(

                self.trim_text(

                    additional_context,

                    self.MAX_CONTEXT_CHARS

                )

            )




        prompt = "\n\n".join(

            p

            for p in parts

            if p

        )




        # Debug

        print(
            "\n===== CYN PROMPT DEBUG ====="
        )


        print(
            "Characters:",
            len(prompt)
        )


        print(
            "Words:",
            len(prompt.split())
        )


        print(
            "Estimated tokens:",
            int(len(prompt.split()) * 1.3)
        )


        print(
            "Active modes:",
            active_modes
        )


        print(
            "Active options:",
            active_options
        )


        print(
            "CYN Studio Loaded:",
            bool(cyn_studio)
        )


        print(
            "Safety Loaded:",
            bool(safety)
        )


        print(
            "Conversation Loaded:",
            bool(conversation)
        )


        print(
            "Examples Loaded:",
            bool(examples)
        )


        print(
            "Projects Loaded:",
            bool(projects)
        )


        print(
            "Reasoning Loaded:",
            bool(reasoning)
        )


        print(
            "============================\n"
        )




        return prompt