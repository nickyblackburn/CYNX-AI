import time
from ai.ollama_client import OllamaClient
from ai.prompt_builder import PromptBuilder
from tools.tool_router import ToolRouter
from tools.SmokeCounterTool import smoke_counter

client = OllamaClient()
builder = PromptBuilder()
router = ToolRouter()
router.register_tool(smoke_counter)
user = 'hey mommy how are u'
full_prompt = builder.build_prompt(
    user_input=user,
    mode_fragment='normal',
    memory_summary='',
    knowledge_context='',
    tools_spec='Available tools:\n' + '\n'.join(f"{t['name']}: {t['description']}" for t in router.describe_tools())
)

success = 0
failures = 0
invalid_names_seen = set()
for i in range(1, 31):
    start = time.perf_counter()
    try:
        resp = client.chat(
            messages=[
                {'role': 'system', 'content': full_prompt},
                {'role': 'user', 'content': user},
            ],
            tools=router.as_ollama_tools(),
            stream=False,
        )
        elapsed = time.perf_counter() - start
        msg = resp.get('message', {})
        content = msg.get('content')
        tool_calls = msg.get('tool_calls') or []
        if tool_calls:
            print(f'ATTEMPT {i} status=200 elapsed={elapsed:.2f}s RESULT=valid tool_call tool={((tool_calls[0].get("function") or {}).get("name"))}')
            success += 1
        elif content and content.strip():
            print(f'ATTEMPT {i} status=200 elapsed={elapsed:.2f}s RESULT=normal content')
            success += 1
        else:
            # Could be a synthetic empty assistant message returned by the client on peg error
            if resp.get('error'):
                print(f'ATTEMPT {i} status=200 elapsed={elapsed:.2f}s RESULT=peg-native-parse-error-handled')
                failures += 1
            else:
                print(f'ATTEMPT {i} status=200 elapsed={elapsed:.2f}s RESULT=empty/unknown')
                success += 1
        # Detect any invalid tool names that may have been logged earlier (we can't see ChatEngine logs here)
        # No direct capture; omitted.
    except Exception as e:
        elapsed = time.perf_counter() - start
        print(f'ATTEMPT {i} status=500 elapsed={elapsed:.2f}s RESULT=HTTP 500')
        print(repr(e))
        failures += 1

print(f'\nSUMMARY successful_requests={success} 500_failures={failures} failure_percentage={((failures / 30) * 100):.2f}%')
