"""Fix license_type: open-weight models should be 'free', not 'license'."""
import json, os, shutil

DATA = r"F:\KAIHATSU\llmcapa\src\llmcapa\data"
INSTALLED = r"F:\Python314\Lib\site-packages\llmcapa\data"

for fname in os.listdir(DATA):
    if not fname.endswith(".json"):
        continue
    fpath = os.path.join(DATA, fname)
    with open(fpath, encoding="utf-8") as f:
        data = json.load(f)
    
    for m in data.get("models", []):
        pricing = m.get("pricing")
        prov = m.get("provider", "")
        mid = m.get("model_id", "").lower()
        
        # Ollama is always free
        if prov == "ollama":
            m["license_type"] = "free"
            continue
        
        # Has pricing with values
        if pricing and isinstance(pricing, dict):
            inp = pricing.get("input_per_1m", -1)
            out = pricing.get("output_per_1m", -1)
            if inp == 0.0 and out == 0.0:
                m["license_type"] = "free"
            elif inp > 0 or out > 0:
                m["license_type"] = "api"
            else:
                m["license_type"] = "unknown"
            continue
        
        # No pricing - check if open-weight
        if pricing is None:
            # Open-weight model families (available for free download)
            open_weight_prefixes = [
                "deepseek", "gemma", "llama", "mistral", "qwen", "phi",
                "granite", "nemotron", "starcoder", "codellama", "codegemma",
                "falcon", "aya", "olmo", "smollm", "tinyllama", "dolphin",
                "yi", "zephyr", "openchat", "vicuna", "wizard", "solar",
                "stable", "stability", "minicpm", "internlm", "exaone",
                "glm", "command", "cohere", "nous", "hermes", "tulu",
                "sailor", "athene", "cogito", "gpt-oss", "sora", "kimi",
                "moonshot", "minimax", "xai", "grok", "sakana", "fugu",
                "tsuzumi", "elyza", "cotomi", "takane", "plamo", "sarashina",
                "cc-gov", "rnj", "ornith", "alfred", "laguna", "magicoder",
                "sqlcoder", "codebooga", "codegeex", "codeup", "opencoder",
                "north-mini", "reader-lm", "nuextract", "paraphrase",
                "mxbai", "bge", "nomic", "snowflake", "jina",
            ]
            is_open = any(mid.startswith(p) or ("/" + p) in mid for p in open_weight_prefixes)
            m["license_type"] = "free" if is_open else "license"
    
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

for fname in os.listdir(DATA):
    if fname.endswith(".json"):
        shutil.copy2(os.path.join(DATA, fname), os.path.join(INSTALLED, fname))

print("Fixed license_type for all JSON files", flush=True)
