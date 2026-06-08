# The Unofficial Guide — Project 1

> **How to use this template:**
> Complete each section *after* you've built and tested the corresponding part of your system.
> Do not write placeholder text — if a section isn't done yet, leave it blank and come back.
> Every section below is required for submission. One-liners will not receive full credit.

---

## Domain

<!-- What topic or category of knowledge does your system cover?
     Why is this knowledge valuable, and why is it hard to find through official channels?
     Example: "Student reviews of CS professors at [university] — useful because official
     course descriptions don't reflect teaching style, exam difficulty, or workload." -->
     The system covers research postion, scholorships, study-abroad programs, internships, and related academic/career openings across departments, centers, and student organizations. 

     Why is this valuable and hard to find? Since most of the details are scattered across departmental pages, faculty sites, event calander, and private channels and are published inconsistently or behind auth/JS widgets. However aggregating and normalizing them lets users ask natural-language questions like "what research positions are open this semester in the College of Science?" and get percise, source-attributed answers without manual searching.


---

## Document Sources

<!-- List every source you collected documents from.
     Be specific: include URLs, subreddit names, forum thread titles, or file names.
     Aim for variety — sources that together cover different subtopics or perspectives. -->

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
 

---

## Chunking Strategy

<!-- Describe your chunking approach with enough specificity that someone else could reproduce it.
     Include:
     - Chunk size (characters or tokens) and why that size fits your documents
     - Overlap size and why (or why not) you used overlap
     - Any preprocessing you did before chunking (e.g., stripping HTML, removing headers)
     - What your final chunk count was across all documents -->

**Chunk size:**
1000

**Overlap:**
150

**Why these choices fit your documents:**
Turns out that most of the info from my data needs to be stored together to answer questions such as "Top 5 ways graduates found jobs?". 

How? well we keeps headings and relevent paragrah near each other and reduces answer spliting across chuncks which makes the recall easier for questions needding several details.

**Final chunk count:**
75 
---

## Embedding Model

<!-- Name the embedding model you used and explain your choice.
     Then answer: if you were deploying this system for real users and cost wasn't a constraint,
     what tradeoffs would you weigh in choosing a different model?
     Consider: context length limits, multilingual support, accuracy on domain-specific text,
     latency, and local vs. API-hosted. -->

**Model used:**
``all-MiniLM-L6-v2 ``

**Production tradeoff reflection:** Maybe a larger/higer-dim models which will increase relevance for paraphrases and domain-specific phrasing. Also using embedding trained on multillingual data if the sources/queries aren't all English.

---

## Grounded Generation

<!-- Explain how your system enforces grounding — how does it prevent the LLM from answering
     beyond the retrieved documents?
     Describe both your system prompt (what instruction you gave the model) and any structural
     choices (e.g., how you formatted the context, whether you filtered low-relevance chunks).
     Do not just say "I told it to use the documents" — show the actual instruction or explain
     the mechanism. -->

**System prompt grounding instruction:**
My system uses a strict system prompt in `query.py` that tells the model to answer only from retrieved context:

> You are a grounded campus opportunities assistant for George Mason University.
>
> Answer the user's question using only the retrieved context below.
> If the context does not contain enough information to answer, say: "I don't know based on the retrieved documents."
> Do not use outside knowledge.
> Do not invent deadlines, eligibility rules, contacts, links, or program details.
> Include source attribution in the answer using bracketed source numbers like [1], [2].
> Keep the answer concise and directly tied to the user's question.

This prevents the model from freely answering from general knowledge. If the retrieved chunks do not contain the answer, the model is explicitly instructed to say it does not know based on the documents.

**How source attribution is surfaced in the response:**
Before generation, the system retrieves candidate chunks from ChromaDB using `all-MiniLM-L6-v2`, then reranks them with a cross-encoder reranker. The answer model only receives the top reranked chunks, not the full document collection.

The retrieved context is formatted as numbered snippets, for example:

``` [1] Source: research@research-opportunities.txt | Chunk: research@research-opportunities.txt::0004 | Distance: 0.4416```
<chunk text>

---

## Evaluation Report

<!-- Run your 5 test questions from planning.md through your system and record the results.
     Be honest — a partially accurate or inaccurate result that you explain well is more
     valuable than a suspiciously perfect result. -->

| # | Question | Expected answer | System response (summarized) | Retrieval quality | Response accuracy |
|---|----------|-----------------|------------------------------|-------------------|-------------------|
| 1 | "What are the top 5 ways Mason graduates found jobs?" | Internships; job sites (Handshake/LinkedIn/Indeed); relationships (faculty/alumni/friends); company/organization websites; networking events/career fairs | The system identified internships and job sites like Handshake, LinkedIn, and Indeed, but did not clearly return all five categories. | Partially relevant  |  Partially accurate |
| 2 | "What does ASSIP stand for?" | Aspiring Scientists Summer Internship Program | The system correctly answered that ASSIP stands for Aspiring Scientists Summer Internship Program and cited the research opportunities source. | Relevant | Accurate |
| 3 | "What types of financial aid does GMU list on the Scholarships page?" | Mason Merit Scholarships, Mason Foundation Scholarships, and other scholarship resources listed by GMU |  The system found Mason Foundation Scholarships, but did not consistently include all scholarship types from the page. | Partially relevant | Partially accurate |
| 4 | "Name three research centers listed in GMU's Research Centers directory." | Examples include Digital Innovation, Institute for Sustainable Earth, and other GMU research centers/institutes | The system retrieved research-center-related context and matched Digital Innovation, but the retrieved evidence only partially covered the expected set of three centers. | Partially relevant | Partially accurate |
| 5 | "What kinds of funding opportunities does GMU list for graduate students?" | Research funding, fieldwork funding, fellowships, grants, and awards | The system retrieved graduate funding context and matched research, fieldwork, and funding-related terms. | Relevant | Accurate |

**Retrieval quality:** Relevant / Partially relevant / Off-target  
**Response accuracy:** Accurate / Partially accurate / Inaccurate

---

## Failure Case Analysis

<!-- Identify at least one question where retrieval or generation did not work as expected.
     Write a specific explanation of *why* it failed, tied to a part of the pipeline.

     "The answer was wrong" is not an explanation.

     "The relevant information was split across a chunk boundary, so retrieval returned
     only half the context — the model didn't have enough to answer correctly" is an explanation.

     "The embedding model treated the professor's nickname as out-of-vocabulary and returned
     results from an unrelated review" is an explanation. -->

**Question that failed:**
What types of financial aid does GMU list on the Scholarships page?

**What the system returned:**
It did not retrieve chunks containing the expected scholarship terms like “Mason Merit Scholarships” or “Mason Foundation Scholarships.

**Root cause (tied to a specific pipeline stage):**
Both Chuncking and reterival stage are to blame as the data from the document is far appart where the overlap and chunck size needs to be enorumous to account for those context and the embedding search returns chunks that are related to financial aid broadly, but not the specific Scholarships page content nedded to answer the quesion.

**What you would change to fix it:**
Improve the source cleaning and chunking for the Scholarships page, and possibly add more targeted metadata or keywords like “scholarships,” “Mason Merit Scholarships,” and “Mason Foundation Scholarships” to make those chunks easier to retrieve.

---

## Spec Reflection

<!-- Reflect on how planning.md shaped your implementation.
     Answer both questions with at least 2–3 sentences each. -->

**One way the spec helped you during implementation:**
The spec helped me break the project into clear pipeline stages: document ingestion, cleaning, chunking, embedding, retrieval, reranking, and grounded generation. Instead of building everything directly into the app, I separated the system into modules like `ingest_documents.py`, `chroma_store.py`, `query.py`, and `app.py`. This made it easier to test each part separately and later add features like the rebuild-index button and retrieval evaluation script.

**One way your implementation diverged from the spec, and why:**
The original planning document described token-based chunking, but my implementation uses character-based chunking with token counts only for filtering and evaluation. I made this change because character-based chunking was simpler to implement locally without adding another tokenizer dependency, and it was easier to tune quickly for my collected documents. After testing, I changed the chunk size from the earlier smaller setting to larger chunks because the documents often needed headings, lists, and surrounding context to stay together for retrieval.

---

## AI Usage

<!-- Describe at least 2 specific instances where you used an AI tool during this project.
     For each: what did you give the AI as input, what did it produce, and what did you
     change, override, or direct differently?

     "I used Claude to help me code" is not sufficient.
     "I gave Claude my Chunking Strategy section from planning.md and asked it to implement
     chunk_text(). It returned a function using a fixed character split. I overrode the
     chunk size from 500 to 200 because my documents are short reviews, not long guides." -->

**Instance 1**

- *What I gave the AI:*
I gave the AI my ingestion plan, including the requirement to load files from `documents/`, clean the text, split it into chunks, and preserve metadata such as `source_name`, `chunk_id`, `chunk_index`, and token count.

- *What it produced:*
 It helped generate the first version of `ingest_documents.py`, including functions for cleaning HTML/text, splitting paragraphs, creating overlapping chunks, filtering very small chunks, and returning chunk records in memory.

- *What I changed or overrode:*
 I changed the chunking settings after testing. The first smaller chunks were not keeping enough context together, so I increased the chunk size to 1000 characters with 150 overlap because my documents often had lists and headings that needed to stay near the relevant details.

**Instance 2**

- *What I gave the AI:*
 I asked the AI to help implement the RAG pipeline after ingestion, including ChromaDB indexing, retrieval, reranking, grounded Groq answer generation, and a Gradio interface.

- *What it produced:*
It helped create `chroma_store.py`, `query.py`, `evaluate_retrieval.py`, `rebuild_index.py`, and `app.py`. These files added embedding with `all-MiniLM-L6-v2`, ChromaDB storage, cross-encoder reranking, evaluation metrics like recall@5 and average tokens retrieved, and a ChatGPT-like UI.

- *What I changed or overrode:*
I adjusted the UI design and functionality based on my preferences, including the darker background, light-blue button, black input text, and a rebuild-index button. I also compared different chunk sizes and decided to use the configuration that gave better retrieval results for my evaluation questions.
