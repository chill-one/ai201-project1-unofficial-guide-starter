# Project 1 Planning: The Unofficial Guide

> Write this document before you write any pipeline code.
> Your spec and architecture diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Update the Retrieval Approach and Chunking Strategy sections if you change your approach during implementation.
> Update this file before starting any stretch features.

---

## Domain

<!-- What domain did you choose? Why is this knowledge valuable and hard to find through official channels? -->
College campus events: cultural days, club meetings, workshops, guest talks, and other on-campus activities.

Why this is valuable and hard to find: event information is scattered across official calendars, department pages, club social media, mailing lists, posters, and private channels (Discord/WhatsApp). Small clubs and ad-hoc groups often post last-minute updates or use inconsistent formats, and official sites frequently omit details (exact room, RSVP links, contact person). Aggregating and normalizing these sources makes it easy to ask natural-language questions like "What events are happening this weekend near the student center?" and get reliable time, location, and RSVP/contact info without manually searching multiple places.

---

## Documents

<!-- List your specific sources: URLs, subreddit names, forum threads, or file descriptions.
     Aim for at least 10 sources that together cover different subtopics or perspectives within your domain. -->

| # | Source | Description | URL or location |
|---|--------|-------------|-----------------|
| 1 | GMU calendar | Central source for larger campus events | https://www.gmu.edu/calendar |
| 2 | Mason360 | Official GMU student-engagement/events & groups platform (Events, Groups, RSVP) | https://mason360.gmu.edu/events|
| 3 | College of Science — Research Opportunities | Departmental research opportunities and student research listings | https://science.gmu.edu/research/research-opportunities |
| 4 | GMU News & Events (The GEORGE) | University announcements, lectures, featured events | https://www.gmu.edu/news |
| 5 | Schar School events | Department-level seminars and public talks (example department) | https://schar.gmu.edu/events |
| 6 | Fourth Estate (student newspaper) | Student coverage and event write-ups | https://gmufourthestate.com |
| 7 | r/gmu (Reddit) | Community posts, informal announcements, student tips | https://www.reddit.com/r/gmu |
| 8 | George Mason Instagram | Fast, last-minute announcements from official accounts | https://www.instagram.com/georgemasonu/ |
| 9 | George Mason Facebook | Official Facebook page and event posts | https://www.facebook.com/georgemason |
|10 | RecWell (Recreation & Wellness) | Fitness classes, intramurals, campus rec events | https://recreation.gmu.edu |
---
 
## Chunking Strategy

<!-- How will you split documents into chunks?
     State your chunk size (in tokens or characters), overlap size, and explain why those
     numbers fit the structure of your documents.
     A review-heavy corpus warrants different chunking than a long FAQ. -->

**Chunk size:**

**Overlap:**

**Reasoning:**

---

## Retrieval Approach

<!-- Which embedding model are you using (e.g., all-MiniLM-L6-v2 via sentence-transformers)?
     How many chunks will you retrieve per query (top-k)?
     If you were deploying this for real users and cost wasn't a constraint, what tradeoffs
     would you weigh in choosing a different embedding model — context length, multilingual
     support, accuracy on domain-specific text, latency? -->

**Embedding model:**

**Top-k:**

**Production tradeoff reflection:**

---

## Evaluation Plan

<!-- List your 5 test questions with their expected correct answers.
     Questions should be specific enough that you can judge whether the system's response
     is right or wrong. "What are good dining halls?" is too vague.
     "What do students say about wait times at [dining hall name] during lunch?" is testable. -->

| # | Question | Expected answer |
|---|----------|-----------------|
| 1 | | |
| 2 | | |
| 3 | | |
| 4 | | |
| 5 | | |

---

## Anticipated Challenges

<!-- What could go wrong? Name at least two specific risks with reasoning.
     Consider: noisy or inconsistent documents, missing source attribution, off-topic
     retrieval, chunks that split key information across boundaries. -->

1.

2.

---

## Architecture

<!-- Draw a diagram of your pipeline showing the five stages:
     Document Ingestion → Chunking → Embedding + Vector Store → Retrieval → Generation
     Label each stage with the tool or library you're using.
     You can use ASCII art, a Mermaid diagram, or embed a sketch as an image.
     You'll use this diagram as context when prompting AI tools to implement each stage. -->

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

**Milestone 4 — Embedding and retrieval:**

**Milestone 5 — Generation and interface:**
