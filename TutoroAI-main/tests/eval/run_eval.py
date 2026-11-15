"""
Tutoro AI eval. Put dataset.py and this file in  tests/eval/  and run from the repo root.

  python tests/eval/run_eval.py collect [--limit 20] [--category fees]   # runs the REAL agent; resumable
  python tests/eval/run_eval.py score                                    # judges + Ragas + tool metrics

What is real vs mocked
  REAL : system prompt, LLM (gpt-oss-120b), tool schemas, FAISS retriever (same one production uses)
  MOCK : Postgres, Redis, Twilio  -> in-memory fakes that RECORD every tool call, so no real bookings happen

Install extras:  pip install ragas datasets pandas tabulate
"""
import argparse, asyncio, json, os, sys, time, types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] if Path(__file__).parent.name == "eval" else Path.cwd()
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
# settings requires these at import time; dummies are fine because DB/Twilio are mocked
for k, v in dict(TWILIO_ACCOUNT_SID="x", TWILIO_AUTH_TOKEN="x", TWILIO_WHATSAPP_NUMBER="whatsapp:+1",
                 DATABASE_URL="postgresql://u:p@localhost/db", GOOGLE_CALENDAR_ID="x").items():
    os.environ.setdefault(k, v)

from dataset import CASES

OUT = Path(__file__).parent / "results"; OUT.mkdir(exist_ok=True)
RUNS, JUDGED, SCORES = OUT / "runs.jsonl", OUT / "judged.jsonl", OUT / "scores.csv"
SLEEP = float(os.getenv("EVAL_SLEEP", "3"))
PHONE = "whatsapp:+60199001122"          # same shape the webhook passes in
JUDGE_MODEL = os.getenv("EVAL_JUDGE_MODEL", "openai/gpt-oss-120b")

FAKE_CLASSES = ("Here are the available classes from our database:\n"
                "- Form 2 Mathematics on Mondays from 14:00 to 15:00 (Class ID: 1)\n"
                "- Form 2 English on Wednesdays from 15:00 to 16:00 (Class ID: 2)\n"
                "- Form 2 Mathematics on Saturdays from 09:00 to 10:00 (Class ID: 3)\n"
                "- Form 1 Bahasa Melayu on Fridays from 16:00 to 17:00 (Class ID: 5)")


# ------------------------------------------------------------------ harness --
def build_instrumented_agent(returning=False, has_booking=False):
    """Import the real agent module, swap DB/Redis for fakes, return an executor that exposes tool calls."""
    import app.agents.sales_agent as sa
    import app.db.redis_client as rc

    lead = types.SimpleNamespace(name="Farah", child_name="Aina", child_age=2, subjects="Mathematics",
                                 email="farah@gmail.com", stage="booked") if returning else None
    booking = types.SimpleNamespace(id=7, notes="Trial Class ID: 3", subjects="Mathematics", status="confirmed")

    async def _get_lead(phone): return lead
    async def _noop(*a, **k): return None
    async def _bookings(phone): return [booking] if has_booking else []
    async def _sched(subject=None): return FAKE_CLASSES

    sa._get_lead, sa._save_lead_async, sa._save_booking_async = _get_lead, _noop, _noop
    sa._get_bookings_async, sa._cancel_booking_async = _bookings, _noop
    sa.get_database_schedule = _sched
    rc.pause_bot = _noop
    sa._db_run = lambda coro: asyncio.run(coro)       # no thread pool needed without a real DB

    sa._agent_executor = None                          # force rebuild so tools see the fakes
    ex = sa.get_agent()
    ex.return_intermediate_steps = True
    ex.verbose = False
    return sa, ex


def run_case(case):
    from langchain_core.messages import HumanMessage, AIMessage
    sa, ex = build_instrumented_agent(case["returning"], case["has_booking"])
    hist = [HumanMessage(content=c) if r == "user" else AIMessage(content=c) for r, c in case["history"]]
    # Mirrors sales_agent.run_agent exactly (including passing `phone`, which the prompt does not use)
    res = ex.invoke({"input": case["question"], "chat_history": hist, "phone": PHONE})
    steps = res.get("intermediate_steps", [])
    calls = [{"tool": a.tool, "args": a.tool_input, "obs": str(o)[:1500]} for a, o in steps]
    contexts = [c["obs"] for c in calls if c["tool"] == "query_knowledge_base"]
    answer = (res.get("output") or "").strip()
    return answer, calls, contexts


def done_ids():
    return {json.loads(l)["id"] for l in RUNS.read_text().splitlines() if l.strip()} if RUNS.exists() else set()


def collect(args):
    todo = [c for c in CASES if c["id"] not in done_ids()]
    if args.category: todo = [c for c in todo if c["category"] == args.category]
    if args.limit: todo = todo[: args.limit]
    print(f"{len(done_ids())} cached, running {len(todo)}")
    with RUNS.open("a") as f:
        for case in todo:
            try:
                ans, calls, ctx = run_case(case)
                rec = {**case, "answer": ans, "calls": calls, "contexts": ctx}
            except Exception as e:
                if "429" in str(e) or "rate" in str(e).lower():
                    print("Rate limited. Stop here and resume later (progress is saved):", str(e)[:120]); break
                rec = {**case, "answer": "", "calls": [], "contexts": [], "error": str(e)[:300]}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n"); f.flush()
            tools = ",".join(c["tool"] for c in rec["calls"]) or "-"
            print(f'{case["id"]} [{case["category"]}] tools={tools} | {(rec["answer"] or rec.get("error",""))[:60]!r}')
            time.sleep(SLEEP)


# -------------------------------------------------------------------- score --
def judge_llm():
    from langchain_groq import ChatGroq
    return ChatGroq(model_name=JUDGE_MODEL, temperature=0.0,
                    groq_api_key=os.getenv("GROQ_JUDGE_API_KEY") or os.environ["GROQ_API_KEY"])


def judge(llm, r):
    """One cheap yes/no call per case. Returns dict(correct|behavior_ok, reason)."""
    if r["gt"]:
        task = (f"Question: {r['question']}\nReference facts: {r['gt']}\nAssistant reply: {r['answer']}\n\n"
                "Does the reply convey the reference facts without contradicting them or inventing "
                "extra prices/policies? Language and formatting differences are fine.")
        key = "correct"
    else:
        task = (f"User message: {r['question']}\nExpected behaviour: {r['behavior']}\nAssistant reply: {r['answer']}\n"
                f"Tools called: {[c['tool'] for c in r['calls']]}\n\nDoes the reply satisfy the expected behaviour?")
        key = "behavior_ok"
    out = llm.invoke(task + '\nAnswer ONLY JSON: {"pass": true|false, "reason": "<=15 words"}').content
    try:
        j = json.loads(out[out.index("{"): out.rindex("}") + 1])
    except Exception:
        j = {"pass": False, "reason": "judge parse error"}
    return {"id": r["id"], key: bool(j["pass"]), "reason": j.get("reason", "")}


def tool_check(r):
    called = {c["tool"] for c in r["calls"]}
    ok_any = (not r["tools_any"]) or bool(called & set(r["tools_any"]))
    ok_none = (not r["tools_none"]) or not (called & set(r["tools_none"]))
    return ok_any and ok_none


def phone_arg_check(r):
    """Did the agent pass the real WhatsApp ID to phone-taking tools?  (None if no such call)"""
    ph = [c["args"].get("phone") for c in r["calls"] if isinstance(c["args"], dict) and "phone" in c["args"]]
    return None if not ph else all(p == PHONE for p in ph)


def score(args):
    import pandas as pd
    runs = [json.loads(l) for l in RUNS.read_text().splitlines() if l.strip()]
    runs = [r for r in runs if not r.get("error")]
    cache = {j["id"]: j for j in map(json.loads, JUDGED.read_text().splitlines())} if JUDGED.exists() else {}
    llm = judge_llm()
    with JUDGED.open("a") as f:
        for r in runs:
            if r["id"] in cache or not (r["gt"] or r["behavior"]): continue
            try: j = judge(llm, r)
            except Exception as e:
                print("Judge stopped (rate limit?):", str(e)[:100]); break
            cache[r["id"]] = j; f.write(json.dumps(j, ensure_ascii=False) + "\n"); f.flush(); time.sleep(1.5)

    rows = []
    for r in runs:
        j = cache.get(r["id"], {})
        rows.append(dict(id=r["id"], category=r["category"], q=r["question"][:50],
                         tool_ok=tool_check(r) if (r["tools_any"] or r["tools_none"]) else None,
                         phone_ok=phone_arg_check(r),
                         correct=j.get("correct"), behavior_ok=j.get("behavior_ok"), reason=j.get("reason", "")))
    df = pd.DataFrame(rows)

    # ---- Ragas on factual cases that actually retrieved context ----
    rag = [r for r in runs if r["gt"] and r["contexts"] and r["answer"]]
    if rag:
        from datasets import Dataset
        from ragas import evaluate, RunConfig
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import Faithfulness, LLMContextPrecisionWithReference
        ds = Dataset.from_dict({"user_input": [r["question"] for r in rag], "response": [r["answer"] for r in rag],
                                "retrieved_contexts": [r["contexts"] for r in rag], "reference": [r["gt"] for r in rag]})
        w = LangchainLLMWrapper(judge_llm())
        res = evaluate(ds, metrics=[Faithfulness(llm=w), LLMContextPrecisionWithReference(llm=w)], llm=w,
                       run_config=RunConfig(max_workers=1, timeout=90, max_retries=3)).to_pandas()
        res.insert(0, "id", [r["id"] for r in rag])
        df = df.merge(res[["id"] + [c for c in res.columns if c in ("faithfulness", "llm_context_precision_with_reference")]],
                      on="id", how="left").rename(columns={"llm_context_precision_with_reference": "context_precision"})
    df.to_csv(SCORES, index=False)

    # ---- report ----
    pct = lambda s: f"{s.dropna().astype(float).mean():.0%} ({int(s.dropna().astype(float).sum())}/{s.notna().sum()})" if s.notna().any() else "n/a"
    print("\n=== OVERALL ===")
    print("Factual correctness :", pct(df.correct))
    print("Behaviour pass      :", pct(df.behavior_ok))
    print("Tool-call accuracy  :", pct(df.tool_ok))
    print("Phone-arg correct   :", pct(df.phone_ok), " <- tools received the real WhatsApp ID")
    for m in ("faithfulness", "context_precision"):
        if m in df: print(f"{m:20}: {df[m].mean():.3f}")
    print("\n=== BY CATEGORY ===")
    g = df.groupby("category").agg(n=("id", "count"), correct=("correct", "mean"), behavior=("behavior_ok", "mean"), tools=("tool_ok", "mean"))
    print(g.round(2).to_string())
    bad = df[(df.correct == False) | (df.behavior_ok == False) | (df.tool_ok == False)]
    print(f"\n=== FAILURES ({len(bad)}) ===")
    print(bad[["id", "category", "q", "tool_ok", "reason"]].to_string(index=False))
    print(f"\nFull table: {SCORES}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("stage", choices=["collect", "score"])
    p.add_argument("--limit", type=int); p.add_argument("--category")
    a = p.parse_args(); {"collect": collect, "score": score}[a.stage](a)
