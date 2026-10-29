"""
Quick diagnostic — run this first to confirm the LLM API works independently.
Usage: python test_llm.py
"""
import os, time
from openai import OpenAI
 
api_key  = os.environ.get("SILICONFLOW_API_KEY", "")
base_url = os.environ.get("SILICONFLOW_BASE_URL", "https://api.siliconflow.com/v1")
model    = os.environ.get("SILICONFLOW_MODEL", "Qwen/Qwen3-8B")
 
print(f"Base URL : {base_url}")
print(f"Model    : {model}")
print(f"Key set  : {'yes' if api_key else 'NO — set SILICONFLOW_API_KEY'}")
print()
 
if not api_key:
    raise SystemExit("Set SILICONFLOW_API_KEY first.")
 
llm = OpenAI(api_key=api_key, base_url=base_url)
 
print("Sending test prompt...")
t0 = time.time()
resp = llm.chat.completions.create(
    model=model,
    max_tokens=100,
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user",   "content": "Reply with exactly: SKILL_MATCH: strong — good skills"},
    ],
)
elapsed = round(time.time() - t0, 1)
text = resp.choices[0].message.content or ""
print(f"Response ({elapsed}s): {text}")
print()
print("LLM API OK" if text else "Empty response — check model name")