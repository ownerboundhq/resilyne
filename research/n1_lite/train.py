"""Small reproducible supervised LoRA experiment; not a production release."""
import argparse
import hashlib
import json
import math
import os
import random
from pathlib import Path

import torch
from huggingface_hub import HfApi
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer, set_seed

ROOT = Path(__file__).resolve().parent
BASE = "HuggingFaceTB/SmolLM2-135M-Instruct"

def read_rows(path):
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    assert rows and all(r["prompt"].strip() and r["answer"].strip() for r in rows)
    return rows

def encode(tokenizer, row):
    prompt = [{"role": "user", "content": row["prompt"]}]
    prefix = tokenizer.apply_chat_template(prompt, tokenize=True, add_generation_prompt=True)
    full = tokenizer.apply_chat_template(prompt + [{"role":"assistant","content":row["answer"]}], tokenize=True, add_generation_prompt=False)
    if full[:len(prefix)] != prefix:
        raise ValueError("Chat template prefix mismatch")
    if len(full) > 192 or len(full) <= len(prefix):
        raise ValueError("Example outside token limits")
    return full, [-100] * len(prefix) + full[len(prefix):]

def batch(examples, pad, device):
    width = max(len(x[0]) for x in examples)
    ids, masks, labels = [], [], []
    for x, y in examples:
        n = width - len(x)
        ids.append(x + [pad]*n)
        masks.append([1]*len(x) + [0]*n)
        labels.append(y + [-100]*n)
    return {k:torch.tensor(v,device=device) for k,v in zip(("input_ids","attention_mask","labels"),(ids,masks,labels))}

@torch.no_grad()
def evaluate(model, examples, pad, device):
    model.eval()
    loss_sum, tokens = 0.0, 0
    for ex in examples:
        b = batch([ex],pad,device)
        n = int((b["labels"][:,1:] != -100).sum())
        loss_sum += float(model(**b).loss)*n
        tokens += n
    return loss_sum/tokens

@torch.no_grad()
def samples(model, tokenizer, rows, device):
    model.eval()
    result=[]
    for row in rows:
        ids=tokenizer.apply_chat_template([{"role":"user","content":row["prompt"]}],tokenize=True,add_generation_prompt=True,return_tensors="pt").to(device)
        output=model.generate(input_ids=ids,attention_mask=torch.ones_like(ids),max_new_tokens=32,do_sample=False,pad_token_id=tokenizer.pad_token_id)
        answer=tokenizer.decode(output[0,ids.shape[1]:],skip_special_tokens=True).strip()
        result.append({"prompt":row["prompt"],"reference":row["answer"],"generated":answer})
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",default="artifacts/n1-lite")
    p.add_argument("--epochs",type=int,default=2)
    p.add_argument("--seed",type=int,default=42)
    p.add_argument("--revision",default=None)
    args=p.parse_args()
    set_seed(args.seed)
    torch.set_num_threads(min(4,os.cpu_count() or 1))
    device="cuda" if torch.cuda.is_available() else "cpu"
    revision=args.revision or HfApi().model_info(BASE).sha
    tokenizer=AutoTokenizer.from_pretrained(BASE,revision=revision)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token=tokenizer.eos_token
    model=AutoModelForCausalLM.from_pretrained(BASE,revision=revision,use_safetensors=True,torch_dtype=torch.float32).to(device)
    model.config.use_cache=False
    tr,va=read_rows(ROOT/"train.jsonl"),read_rows(ROOT/"validation.jsonl")
    assert not ({r["prompt"] for r in tr}&{r["prompt"] for r in va})
    training=[encode(tokenizer,r) for r in tr]
    validation=[encode(tokenizer,r) for r in va]
    pad=tokenizer.pad_token_id
    before=evaluate(model,validation,pad,device)
    before_samples=samples(model,tokenizer,va[:4],device)
    model=get_peft_model(model,LoraConfig(r=8,lora_alpha=16,lora_dropout=0.05,target_modules=["q_proj","v_proj"],task_type="CAUSAL_LM"))
    model.print_trainable_parameters()
    opt=torch.optim.AdamW([v for v in model.parameters() if v.requires_grad],lr=2e-4)
    rng=random.Random(args.seed)
    losses=[]
    for epoch in range(args.epochs):
        model.train()
        order=list(range(len(training)));rng.shuffle(order)
        for j in range(0,len(order),2):
            b=batch([training[i] for i in order[j:j+2]],pad,device)
            opt.zero_grad(set_to_none=True)
            loss=model(**b).loss
            if not torch.isfinite(loss):raise RuntimeError("Nonfinite training loss")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(),1.0)
            opt.step()
            losses.append(float(loss))
            print(f"epoch={epoch+1} step={len(losses)} loss={losses[-1]:.4f}",flush=True)
    after=evaluate(model,validation,pad,device)
    after_samples=samples(model,tokenizer,va[:4],device)
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    model.save_pretrained(out/"adapter",safe_serialization=True)
    tokenizer.save_pretrained(out/"adapter")
    report={"experiment":"Neuravale N1 Lite SFT 001","base":BASE,"base_revision":revision,"base_license":"Apache-2.0","device":device,"seed":args.seed,"epochs":args.epochs,"training_examples":len(tr),"validation_examples":len(va),"steps":len(losses),"train_losses":losses,"validation_loss_before":before,"validation_loss_after":after,"heldout_loss_improved":after<before,"base_samples":before_samples,"adapted_samples":after_samples,"data_sha256":{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ("train.jsonl","validation.jsonl")},"limitations":"Tiny synthetic dataset; held-out loss is not a general capability benchmark. No production release."}
    (out/"report.json").write_text(json.dumps(report,indent=2))
    print(json.dumps({k:report[k] for k in ("steps","validation_loss_before","validation_loss_after","heldout_loss_improved")}),flush=True)
    print("Adapter saved.",flush=True)

if __name__=="__main__":main()
