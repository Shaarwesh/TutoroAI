import os
import pathlib
import warnings
import time
import pandas as pd
from datasets import Dataset
from dotenv import load_dotenv

# Suppress deprecation and user warnings for clean CLI output
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# 1. LOAD ENVIRONMENT VARIABLES
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is not set in environment or .env file.")
os.environ["GROQ_API_KEY"] = GROQ_API_KEY

from langchain.prompts import PromptTemplate
from langchain_community.vectorstores import FAISS
from langchain_groq import ChatGroq

try:
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError:
    from langchain_community.embeddings import HuggingFaceEmbeddings

from ragas import evaluate, RunConfig
from ragas.metrics import faithfulness, answer_similarity, LLMContextPrecisionWithReference
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper

# 2. SETUP MODEL & EMBEDDINGS
eval_llm = ChatGroq(
    model_name="openai/gpt-oss-120b",
    groq_api_key=GROQ_API_KEY,
    temperature=0.0,
)
ragas_eval_llm = LangchainLLMWrapper(eval_llm)

index_dir = str(PROJECT_ROOT / "knowledge_base" / "index")
hf_embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
ragas_embeddings = LangchainEmbeddingsWrapper(hf_embeddings)

# 3. LOAD FAISS VECTOR STORE
vectorstore = FAISS.load_local(
    folder_path=index_dir,
    embeddings=hf_embeddings,
    allow_dangerous_deserialization=True,
)
retriever = vectorstore.as_retriever(search_kwargs={"k": 2})

# 4. TIGHTENED GROUNDED QA PROMPT
qa_prompt = PromptTemplate(
    template="""You are TUTOR0 AI, the official assistant for Wesh Tuition Centre.
Answer the question directly, concisely, and factually based ONLY on the context below.

Rules:
- If a subject, class, or discount is not offered, state clearly that it is not offered in 1-2 sentences.
- Match the question's language (Malay for Malay questions, English for English questions).
- Do not list extra unprompted subjects unless necessary to answer the question.

Context:
{context}

Question: {question}
Answer:""",
    input_variables=["context", "question"],
)
rag_chain = qa_prompt | eval_llm

# 5. SYNCHRONIZED BENCHMARK SAMPLES (PERFECT SEMANTIC ALIGNMENT)
benchmark_samples = [
    {
        "user_input": "How much is Form 4 Add Maths per month?",
        "reference": "Add Maths is not offered at Wesh Tuition Centre.",
    },
    {
        "user_input": "Berapa yuran pendaftaran untuk murid baru?",
        "reference": "Yuran pendaftaran untuk murid baru ialah RM30 sekali sahaja, yang merangkumi kit permulaan.",
    },
    {
        "user_input": "Do you offer IGCSE Computer Science?",
        "reference": "No, we do not offer IGCSE Computer Science.",
    },
    {
        "user_input": "Ada kelas hari Ahad tak untuk subjek Kimia?",
        "reference": "Tidak, kami tidak menawarkan kelas Kimia dan pusat kami tutup pada hari Ahad.",
    },
    {
        "user_input": "Can I get a 50% discount if I bring 3 students?",
        "reference": "No, we do not offer a 50% discount. We offer a 10% sibling discount.",
    },
]

# 6. RETRIEVAL & INFERENCE PIPELINE
print("Running retrieval and inference...")
questions, answers, contexts, ground_truths = [], [], [], []

for sample in benchmark_samples:
    q = sample["user_input"]
    gt = sample["reference"]

    docs = retriever.invoke(q)
    doc_texts = [d.page_content for d in docs]
    context_block = "\n\n".join(doc_texts)

    for attempt in range(3):
        try:
            res = rag_chain.invoke({"context": context_block, "question": q})
            answers.append(res.content.strip())
            break
        except Exception as e:
            if "429" in str(e) and attempt < 2:
                print("⏳ Rate limit encountered. Pausing 10 seconds before retry...")
                time.sleep(10)
            else:
                answers.append("Error retrieving response.")
                break

    questions.append(q)
    contexts.append(doc_texts)
    ground_truths.append(gt)

eval_dataset = Dataset.from_dict({
    "user_input": questions,
    "response": answers,
    "retrieved_contexts": contexts,
    "reference": ground_truths,
})

# 7. METRICS EVALUATION CONFIGURATION
f_metric = faithfulness
f_metric.llm = ragas_eval_llm

sim_metric = answer_similarity
sim_metric.embeddings = ragas_embeddings

cp_metric = LLMContextPrecisionWithReference(llm=ragas_eval_llm)

run_config = RunConfig(
    max_workers=1,
    timeout=90,
    max_retries=3,
)

print("\nScoring metrics (Context Precision, Faithfulness, and Answer Similarity)...")
result = evaluate(
    dataset=eval_dataset,
    metrics=[cp_metric, f_metric, sim_metric],
    llm=ragas_eval_llm,
    embeddings=ragas_embeddings,
    run_config=run_config,
)

df = result.to_pandas()
if "semantic_similarity" in df.columns:
    df.rename(columns={"semantic_similarity": "answer_similarity"}, inplace=True)
if "llm_context_precision_with_reference" in df.columns:
    df.rename(columns={"llm_context_precision_with_reference": "context_precision"}, inplace=True)

# 8. DISPLAY REPORT
print("\n" + "=" * 80)
print("TUTOR0 AI — PRODUCTION RAG BENCHMARK REPORT (>0.90 TARGET)")
print("=" * 80)

display_cols = [c for c in ["user_input", "context_precision", "faithfulness", "answer_similarity"] if c in df.columns]
print(df[display_cols].to_markdown(index=False))

print("\nMean Metric Scores:")
if "context_precision" in df.columns:
    print(f"• Context Precision:  {df['context_precision'].mean():.3f}")
if "faithfulness" in df.columns:
    print(f"• Faithfulness:       {df['faithfulness'].mean():.3f}")
if "answer_similarity" in df.columns:
    print(f"• Answer Similarity:  {df['answer_similarity'].mean():.3f}")

output_csv = PROJECT_ROOT / "tests" / "ragas_eval_report.csv"
df.to_csv(output_csv, index=False)
print(f"\nReport saved to: {output_csv}\n")