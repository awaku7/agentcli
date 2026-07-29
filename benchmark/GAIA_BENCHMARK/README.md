# GAIA Benchmark Dataset (Validation Split)

This directory contains the complete **GAIA (General AI Assistants) Benchmark** validation dataset (165 tasks) formatted for agent and LLM evaluation.

## Directory Structure

```
benchmark/GAIA_BENCHMARK/
├── metadata.jsonl         # All 165 validation tasks with questions, ground truth, and metadata
├── attachments/           # All 38 attached files (Excel, PDF, Images, Audio, Docx, Zip, etc.)
└── README.md              # Instructions for benchmark runners
```

## Task Format (`metadata.jsonl`)

Each line in `metadata.jsonl` is a JSON object with the following schema:

```json
{
  "task_id": "32102e3e-d12a-4209-9163-7b3a104efe5d",
  "Question": "The attached spreadsheet shows the inventory...",
  "Level": 2,
  "Final answer": "Time-Parking 2: Parallel Universe",
  "file_name": "32102e3e-d12a-4209-9163-7b3a104efe5d.xlsx",
  "Annotator Metadata": { ... }
}
```

- **`Question`**: The task prompt/instructions to give to the LLM agent.
- **`file_name`**: If non-empty, the corresponding file is located in `attachments/<file_name>`.
- **`Final answer`**: The ground truth answer used for accuracy evaluation.

## How to Evaluate Other LLMs / Agents

1. Load tasks from `metadata.jsonl`.
2. For each task, pass `Question` (and provide access to `attachments/<file_name>` if `file_name` is present) to the target LLM / Agent.
3. Compare the generated output against `Final answer` using normalized exact match (ignoring case, leading/trailing whitespace, quotes, and commas in numbers).
