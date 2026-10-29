# Tools

All tools below are served by `src/tools/job_db.py` as an MCP subprocess
accessible to the Coordinator Agent over stdio. The Compliance, Recruiter, and
Culture Fit agents have no direct access to these tools.

get_job_requirements: Accepts job_id (str) — either a fictional posting ID
(SWE-001, PM-002, DS-003) or a natural language query when RAPIDAPI_KEY is set.
Returns title, company, required_skills (list), preferred_skills (list),
min_experience_years (int), salary_range_usd ([int, int]),
job_offers_sponsorship (bool), description (str), source ("live" or "fallback").

search_jobs: Accepts query (str) and max_results (int, default 3). Searches
JSearch (RapidAPI) for live job postings matching the query. Returns a list of
results each with title, company, location, posted date, and a use_as_job_id
string to pass to get_job_requirements. Requires RAPIDAPI_KEY environment variable;
returns an error dict if key is absent.

lookup_skill_equivalence: Accepts skill (str). Maps informal or abbreviated skill
names to standard canonical names (e.g. "k8s" → "Kubernetes", "ml" → "machine
learning"). Returns input (str), canonical (str), alias_matched (bool).

check_work_authorization: Accepts country_code (str, 2-letter ISO). Returns
requires_sponsorship (bool) and a note (str) based on standard US work
authorization rules. Does not accept or return any candidate-identifying information.

calculate_experience_score: Accepts years_required (int) and years_actual (float).
Returns score (int, 0–100), meets_minimum (bool), ratio (float). Score is computed
as min(100, ratio × 70 + 20) where the +20 bonus applies when ratio ≥ 1.0.
