# PRFAQ: BRD-to-Engineering System Generator (Python)

## Press Release
**Title:** BRDs to execution-ready plans in minutes — powered by Python agents

**Summary:**  
The BRD-to-Engineering System Generator is a Python-based agentic system that
turns business requirement documents into structured engineering plans, schedules,
architecture drafts, PoC scopes, and tech stack recommendations. It reduces manual
drafting time, standardizes outputs, and provides a simple review UI for EMs.

**Customer Quote:**  
"We can now go from a raw BRD to a full engineering plan in one session. The
outputs are consistent, structured, and easy to review."

**Key Benefits:**
- Faster BRD-to-plan turnaround with structured outputs.
- Standardized artifacts across teams.
- Lightweight UI for review and export.

---

## FAQ

**Q: Who is this for?**  
A: Engineering Managers and Tech Leads who need to transform BRDs into plans
and architecture quickly.

**Q: What does it generate?**  
A: Engineering plan, schedule estimate, solution architecture, PoC plan, and
tech stack recommendations.

**Q: How does it work?**  
A: A parser extracts BRD sections, then agent prompts generate artifacts, which
are validated with guardrails and rendered in the UI.

**Q: Is this production-ready?**  
A: It’s an MVP with prompt-driven outputs, fallbacks, and a simple UI. Production
hardening would add stronger validation, observability, and integrations.

**Q: What models are supported?**  
A: OpenAI Chat models via the OpenAI Python SDK.

**Q: How do you control output quality?**  
A: Prompt templates, a strict system prompt, and guardrail checks; fallbacks ensure
valid JSON on errors.

**Q: What is the ROI?**  
A: For typical BRDs, the system can reduce planning and architecture drafting time
by 60–80%, saving EM hours each sprint. The ROI grows with reuse of standardized
outputs and reduced rework from missing assumptions.

**Q: Can it parse PDFs or Word docs?**  
A: Not yet in the Python MVP; the current parser expects text/Markdown. PDF/DOCX
support can be added next.

**Q: How is the API key managed?**  
A: Via `.env` using `OPENAI_API_KEY`.
