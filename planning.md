# Project 1 Planning: The Unofficial Guide

> Write this document before you write any pipeline code.
> Your spec and architecture diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Update the Retrieval Approach and Chunking Strategy sections if you change your approach during implementation.
> Update this file before starting any stretch features.

---

## Domain

<!-- What domain did you choose? Why is this knowledge valuable and hard to find through official channels? -->
College campus opportunities: research positions, scholarships, study abroad programs, internships, and other academic and career opportunities.

Why this is valuable and hard to find: opportunity information is scattered across department pages, research group sites, scholarship portals, study‑abroad pages, faculty webpages, mailing lists, and private channels (Discord/WhatsApp). Individual research groups, scholarship offices, and faculty often publish eligibility, deadlines, or contact details inconsistently, and official pages frequently omit key fields (application links, advisor contact, or deadline). Aggregating and normalizing these sources makes it easy to ask natural-language questions like "What research positions are open this semester in the College of Science?" and get reliable eligibility, deadline, and contact info without manually searching multiple places.

---

## Documents

<!-- List your specific sources: URLs, subreddit names, forum threads, or file descriptions.
     Aim for at least 10 sources that together cover different subtopics or perspectives within your domain. -->

| # | Source | Description | URL or location |
|---|--------|-------------|-----------------|
| 1 | GMU Financial Aid — Scholarships | Official Mason scholarship listings and university scholarship portal | https://www.gmu.edu/financial-aid/types-aid/scholarships |
| 2 | Student Life — Student Organizations & Involvement | Public student-life resources and links to student organizations and opportunities | https://www.gmu.edu/student-life |
| 3 | GMU Research / Office of Research | Central research office: funding opportunities, centers, research news | https://www.gmu.edu/research |
| 4 | College of Science — Research Opportunities | Departmental research opportunities and student research listings | https://science.gmu.edu/research/research-opportunities |
| 5 | Global Education Office (Study Abroad) | Study abroad programs, scholarships, deadlines, and application portal | https://studyabroad.gmu.edu |
| 6 | University Career Services | Internships, employer listings, Handshake, and career scholarships/events | https://careers.gmu.edu/find-job-or-internship |
| 7 | University Career Services — Events | Career-focused events, workshops, and employer fairs (useful for internships and opportunity discovery) | https://careers.gmu.edu/events |
| 8 | Research Centers Directory | University research centers and institutes (central directory of centers/labs) | https://www.gmu.edu/research/research-centers |
| 9 | Graduate Fellowships & Grants (Grad School) | Funding opportunities for graduate students and fellowship listings | https://graduate.gmu.edu/financial-support/grants-fellowships-awards |
|10 | External Scholarship Resources & Student News | Mason news, student newspaper, and external scholarship aggregators | https://www.gmu.edu/news; https://gmufourthestate.com/category/news/ |
|11 | Financial Aid — Eligibility | Financial aid eligibility rules and links (parents/students) | https://www.gmu.edu/financial-aid-parent/eligibility |
---
 
## Chunking Strategy

<!-- How will you split documents into chunks?
     State your chunk size (in tokens or characters), overlap size, and explain why those
     numbers fit the structure of your documents.
     A review-heavy corpus warrants different chunking than a long FAQ. -->

**Chunk size:**
300 tokens

**Overlap:**
60 tokens

**Reasoning:**

- Smaller chunks improve retrieval precision but increase vector count and cost. Larger chunks provide more context but can dilute relevance.
- Overlap prevents important short facts from being split across chunks (critical for deadline/contact extraction).
- Use semantic splitting where possible: prefer headings/paragraphs/list-items and sentence-aware splitters rather than blind fixed-window cuts.
- Extract structured fields (deadline, contact, application link, eligibility) into chunk metadata to avoid loss through chunking.

Practical splitter algorithm (high-level):
1. Render JS pages when needed (headless browser) and extract relevant DOM sections.
2. Clean boilerplate (nav/footer) and normalize text.
3. Split at semantic boundaries (headings, lists, paragraphs). Within a section, sentence-split and accumulate sentences to the target token count; emit chunk when reached.
4. Keep the last N tokens as overlap when emitting a chunk and continue.
5. Attach metadata: `source_url`, `section_heading`, `chunk_index`, `crawl_date`, `published_date`, and structured fields like `deadline` / `contact` / `apply_link`.

Experiment to select optimal size for this corpus:
1. Build a validation set of ~20 representative pages (research listings, career pages, study-abroad program pages, scholarship pages).
2. Index three configs:
     - A: 200 tokens / 40 overlap
     - B: 300 tokens / 60 overlap (default)
     - C: 600 tokens / 100 overlap
3. Run a suite of ~10 benchmark QA queries requiring grounding (deadlines, eligibility, contacts).
4. Measure: answer accuracy (manual/golden check), retrieval recall@5, average tokens retrieved per query (cost proxy), and index size (vector count).
5. Choose the config that gives highest accuracy with acceptable cost; if tied, prefer smaller chunks for better fact pinpointing.

Starting config for this project: **300 tokens / 60 tokens overlap**, semantic splits at headings/paragraphs, and structured-field extraction for deadlines/contacts/links.

---

## Retrieval Approach

<!-- Which embedding model are you using (e.g., all-MiniLM-L6-v2 via sentence-transformers)?
     How many chunks will you retrieve per query (top-k)?
     If you were deploying this for real users and cost wasn't a constraint, what tradeoffs
     would you weigh in choosing a different embedding model — context length, multilingual
     support, accuracy on domain-specific text, latency? -->

**Embedding model:**
all-MiniLM-L6-v2 

**Top-k:**
50

**Production tradeoff reflection:**

Maybe a larger/higer-dim models increase relevance for paraphrases and domain-specific phrasing. Also using embedding trained on multillingual data if the sources/queries aren't all English.
---

## Evaluation Plan

<!-- List your 5 test questions with their expected correct answers.
     Questions should be specific enough that you can judge whether the system's response
     is right or wrong. "What are good dining halls?" is too vague.
     "What do students say about wait times at [dining hall name] during lunch?" is testable. -->

| # | Question | Expected answer |
|---|----------|-----------------|
| 1 | "What are the top 5 ways Mason graduates found jobs? | "Internships; job sites (Handshake/LinkedIn/Indeed); relationships (faculty/alumni/friends); company/organization websites; networking events/career fairs" |
| 2 | "What does ASSIP stand for?" | "Aspiring Scientists Program" |
| 3 | "What types of financial aid does GMU list on the Scholarships page?" | "Mason Merit Scholarships, Mason Foundation Scholarships, ..."|
| 4 | "Name three research centers listed in GMU's Research Centers directory." | "Institute for Sustainable Earth, Digital InnovAtion, ..."|
| 5 | "What kinds of funding opportunities does GMU list for graduate students?" | "Research, FieldWork, ..." |

---

## Anticipated Challenges

<!-- What could go wrong? Name at least two specific risks with reasoning.
     Consider: noisy or inconsistent documents, missing source attribution, off-topic
     retrieval, chunks that split key information across boundaries. -->

1. **Inconsistent structure:** Departments and faculty pages vary widely; deadlines, contacts, or apply links may be ommited or embedded in images, so
automated extractors will miss or mislabel critical fields.

2. **Noisy:** News, blogs and event pages include promotional or unrelated text that can pollute embeddings and surface irrelevant results, increasing hallucination risk.

---

## Architecture

<!-- Draw a diagram of your pipeline showing the five stages:
     Document Ingestion → Chunking → Embedding + Vector Store → Retrieval → Generation
     Label each stage with the tool or library you're using.
     You can use ASCII art, a Mermaid diagram, or embed a sketch as an image.
     You'll use this diagram as context when prompting AI tools to implement each stage. -->
![RAG diagram ](./RAG%20Document%20Retrieval-2026-06-07-213028.png)
---

## AI Tool Plan

<!-- For each part of the pipeline below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, which requirements)
     - What you expect it to produce
     - How you'll verify the output matches your spec

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Chunking Strategy section and ask it to implement chunk_text()
     with my specified chunk size and overlap" is a plan. -->

**Milestone 3 — Ingestion and chunking:**
Implement a robust ingestion pipeline that fetches/renders pages (requests + Playwright), cleans boilerplate, and produces semantic chunks via ``chunk_text()`` using the 300-token / 60-token overlap strategy while extracting metadata (deadline, contact, apply_link); provide ``ingest_sample.py`` and unit tests to verify chunk sizes, overlap, and metadata presence on the validation set.

**Milestone 4 — Embedding and retrieval:**
Chunks with ``all-MiniLM-L6-v2`` and index into ChromaDB via ``embed_and_index()``; implement ``retrieve(query, top_k=50)`` plus a ``rerank()`` (cross-encoder) for top-5 refinement, and include scripts to rebuild the index and report recall@5, vector count, and avg tokens retrieved.

**Milestone 5 — Generation and interface:**
Build ``generate_answer()`` that assembles top evidence with inline citations into a prompt template, calls on claud to produce concise, source-attributed answers, and expose it via app.py (FastAPI) withe end-to-end tests checking correctness, citation presence, and acceptable latency.
