"""
Run adversarial prompts against Pawa-Gemma-Swahili-2B and build the
Zindi submission markdown.

Usage:
    python run_attacks.py --team YOUR_TEAM_NAME

Outputs:
    submission.md  (upload this to Zindi)
    raw_responses.json (for your own records)
"""
import argparse
import json
import os
from pathlib import Path

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

from attacks import ATTACKS

MODEL_ID = "sartifyllc/Pawa-Gemma-Swahili-2B"
TARGET_MODEL_LABEL = "sartifyllc/Pawa-Gemma-Swahili-2B"
OUT_DIR = Path(__file__).parent


def load_model():
    print(f"[+] Loading tokenizer: {MODEL_ID}")
    tok = AutoTokenizer.from_pretrained(MODEL_ID)
    print(f"[+] Loading model: {MODEL_ID} (this may take a while on first run)")
    dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        dtype=dtype,
        device_map="auto" if torch.cuda.is_available() else None,
        low_cpu_mem_usage=True,
    )
    model.eval()
    return tok, model


def generate(tok, model, prompt: str, max_new_tokens: int = 350) -> str:
    # Try a chat template first; fall back to plain text.
    try:
        messages = [{"role": "user", "content": prompt}]
        input_ids = tok.apply_chat_template(
            messages, add_generation_prompt=True, return_tensors="pt"
        ).to(model.device)
    except Exception:
        input_ids = tok(prompt, return_tensors="pt").input_ids.to(model.device)

    with torch.no_grad():
        out = model.generate(
            input_ids,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
            repetition_penalty=1.1,
            pad_token_id=tok.eos_token_id,
        )
    # strip the prompt prefix
    gen = out[0][input_ids.shape[-1]:]
    text = tok.decode(gen, skip_special_tokens=True).strip()
    return text


def build_markdown(team: str, results: list) -> str:
    lines = []
    lines.append("# Zindi - African Trust & Safety LLM Challenge Submission\n")
    lines.append("## Participant Info")
    lines.append(f"- **Team / User Name:** {team}\n")
    lines.append("---\n")

    for i, r in enumerate(results, 1):
        lines.append(f"## Attack {i}\n")
        lines.append("### Metadata")
        lines.append(f"- **Attack ID:** {r['id']}")
        lines.append(f"- **Target Model:** {TARGET_MODEL_LABEL}")
        lines.append(f"- **Language:** Swahili")
        lines.append(f"- **Attack Type:** {r['attack_type']}")
        lines.append(f"- **Risk Category:** {r['risk_category']}")
        lines.append(f"- **Risk Subcategory:** {r['risk_subcategory']}\n")

        lines.append("### Adversarial Prompt (Original Language)")
        lines.append("```")
        lines.append(r["prompt_sw"])
        lines.append("```\n")

        lines.append("### Adversarial Prompt (English)")
        lines.append("```")
        lines.append(r["prompt_en"])
        lines.append("```\n")

        lines.append("### Target Model Response")
        lines.append("```")
        lines.append(r["response"].strip() or "[empty response]")
        lines.append("```\n")

        lines.append("### Contextual Notes")
        lines.append(r["notes"])
        lines.append("\n---\n")

    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", required=True, help="Your Zindi team/user name")
    ap.add_argument("--out", default=str(OUT_DIR / "submission.md"))
    ap.add_argument("--raw", default=str(OUT_DIR / "raw_responses.json"))
    ap.add_argument("--max-new-tokens", type=int, default=350)
    args = ap.parse_args()

    tok, model = load_model()

    results = []
    for a in ATTACKS:
        print(f"\n=== {a['id']} [{a['attack_type']} / {a['risk_category']}] ===")
        try:
            resp = generate(tok, model, a["prompt_sw"], max_new_tokens=args.max_new_tokens)
        except Exception as e:
            resp = f"[generation error: {e}]"
        print(resp[:300])
        results.append({**a, "response": resp})

    # Save raw JSON
    with open(args.raw, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n[+] Wrote raw responses to {args.raw}")

    # Build markdown
    md = build_markdown(args.team, results)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"[+] Wrote submission markdown to {args.out}")


if __name__ == "__main__":
    main()
