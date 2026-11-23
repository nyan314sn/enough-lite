"""Research agent: rule questions answered only from cited official passages (keyword retrieval).

In a plan run it looks up the two or three rules that matter most for this household. For /api/ask it answers a rule
question from the passages, or says "I don't have a source for that."
"""
from __future__ import annotations

import json

from pydantic import BaseModel, Field
from pydantic_ai import RunContext

from .. import llm, safety
from ..tools import sources
from .base import STYLE, Finding, RunCtx, Specialist, tool_event

NO_SOURCE = "I don't have a source for that."


def default_queries(ctx: RunCtx) -> list[str]:
    p = ctx.profile
    age, ra = p.age or 45, p.retire_age or 65
    q = []
    if age < ra:
        q.append("401(k) contribution limit catch-up age 50" if age >= 45 else "401(k) contribution limit 2027")
    q.append("delayed retirement credits claiming Social Security after full retirement age")
    if ra < 65 or age >= 60:
        q.append("Medicare enrollment age 65 when coverage starts")
    if age >= 65:
        q.append("required minimum distribution start age")
    return q[:3]


async def search_tool(ctx: RunCtx, query: str, agent: str = "research") -> list[dict]:
    hits = sources.search(query, k=3)
    bucket = ctx.results.setdefault("research", {"queries": [], "passages": []})
    bucket["queries"].append(query)
    for h in hits:
        if all(h["id"] != x["id"] for x in bucket["passages"]):
            bucket["passages"].append(h)
            ctx.extra_facts.extend([h["title"], h["text"]])
            if all(h["url"] != c["url"] for c in ctx.citations):
                ctx.citations.append({"title": h["title"], "url": h["url"], "id": h["id"]})
    await tool_event(ctx, agent, "search_sources", f'"{query[:60]}": {len(hits)} passage(s) found.')
    return [{"id": h["id"], "title": h["title"], "text": h["text"]} for h in hits]


class Research(Specialist):
    name = "research"
    label = "Rules and sources"
    tool_name = "search_sources"
    tool_doc = "Search short official passages (IRS, SSA, Medicare) for a rule. Returns passages with ids."
    instructions = ("You are the research specialist in a retirement-planning team. Official passages are given with the request. "
                    "Pick the two or three rules that matter most to this household (for example contribution limits, Social "
                    "Security claiming, Medicare at 65, required distributions). State each rule only as a passage states it. "
                    "Say each rule in plain everyday words, not the passage's legal wording. "
                    "Search again only if no passage covers a rule you need. If none covers it, leave it out.")

    def compute(self, ctx: RunCtx) -> dict:  # used only by ensure()
        return {}

    async def ensure(self, ctx: RunCtx) -> dict:
        if not ctx.results.get("research", {}).get("passages"):
            for q in default_queries(ctx):
                await search_tool(ctx, q)
        bucket = ctx.results.setdefault("research", {"queries": [], "passages": []})
        p = ctx.profile
        age, ra = p.age or 45, p.retire_age or 65
        about = {"age_now": age, "retire_age": ra}
        if ra > age:
            about["years_to_retire"] = ra - age
        if age < 65:
            about["years_to_65"] = 65 - age
        if age < ra and ra < 65:
            about["years_without_medicare_after_retiring"] = 65 - ra
        bucket["about_you"] = about
        return bucket

    def tool_list(self):
        async def run(ctx: RunCtx, query: str = "") -> list[dict]:
            return await search_tool(ctx, query or "retirement rules")
        return [(self.tool_name, self.tool_doc, run)]

    def build(self):
        from pydantic_ai import Agent

        agent = Agent(llm.make_model(), output_type=Finding, deps_type=RunCtx,
                      instructions=self.instructions + "\n\n" + STYLE, name=self.name)

        @agent.tool
        async def search_sources(rc: RunContext[RunCtx], query: str) -> list[dict]:
            """Search short official passages (IRS, SSA, Medicare) for a rule. Returns passages with ids."""
            return await search_tool(rc.deps, query)

        return agent

    def prompt(self, ctx: RunCtx, r: dict) -> str:
        p = ctx.profile
        facts = {"age": p.age, "partner_age": p.partner_age, "retire_age": p.retire_age, "working": (p.retire_age or 65) > (p.age or 45)}
        passages = "\n".join(f"[{x['id']}] {x['title']}: {x['text']}" for x in r.get("passages", []))
        return (f"Passages:\n{passages}\n\nNumbers you may use (the figures in the passages, and these about the household):\n"
                + "\n".join(self.figures(ctx, r)) + f"\n\nHousehold facts: {json.dumps(facts)}. Write the finding.")

    def figures(self, ctx: RunCtx, r: dict) -> list[str]:
        from .base import figure_lines
        seen, passage = set(), []
        for x in r.get("passages", []):
            for _, _, raw in safety.numbers_in(x["title"] + " " + x["text"]):
                if raw not in seen:
                    seen.add(raw)
                    passage.append(raw)
        return (["- in the passages: " + ", ".join(passage)] if passage else []) + figure_lines(r.get("about_you", {}))

    def numbers(self, r: dict) -> dict:
        figures = [v for x in r.get("passages", []) for v, _, _ in safety.numbers_in(x["title"] + " " + x["text"])]
        return {"passages_found": len(r.get("passages", [])), "passage_figures": figures, **r.get("about_you", {})}

    def template(self, r: dict) -> tuple[str, list[str]]:
        ps = r.get("passages", [])
        if not ps:
            return NO_SOURCE, []
        return ("These rules matter most for you.", [f"{x['title']}." for x in ps[:3]])


class Answer(BaseModel):
    kind: str = Field(description='"answer" when the passages or the plan figures answer the question; "no_source" when they do not.')
    text: str = Field(description="The answer in one to three short sentences (15 words each, 45 in all), in plain words. "
                                  "Only figures from the passages or the plan.")
    source_ids: list[str] = Field(default_factory=list, description="Ids of the passages the answer relies on.")


ASK_INSTRUCTIONS = (
    "You answer one question from a person using a retirement plan. Rule questions (tax, IRA, 401(k), Social Security, "
    "Medicare, required distributions) must be answered only from passages found with search_sources; cite their ids. "
    "Questions about the plan are answered only from the plan figures given. If neither covers the question, set kind to "
    "no_source. Never give advice on hiding or moving assets to qualify for Medicaid or SSI. " + STYLE)


def build_ask_agent():
    from pydantic_ai import Agent


    agent = Agent(llm.make_model(), output_type=Answer, deps_type=RunCtx, instructions=ASK_INSTRUCTIONS, name="ask")

    @agent.tool
    async def search_sources(rc: RunContext[RunCtx], query: str) -> list[dict]:
        """Search short official passages (IRS, SSA, Medicare) for a rule. Returns passages with ids."""
        return await search_tool(rc.deps, query, agent="ask")

    return agent


def ask_prompt(question: str, plan_summary: dict) -> str:
    return (safety.wrap_untrusted(question, "question") + "\n" +
            safety.wrap_untrusted(json.dumps(plan_summary), "plan_figures") +
            "\nAnswer the question. Search at most twice.")
