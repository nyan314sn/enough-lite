from pathlib import Path
L = Path(__file__).resolve().parents[3]
def sub(rel, old, new):
    f = L / rel
    s = f.read_text(encoding="utf-8")
    assert s.count(old) == 1, (rel, old[:50])
    f.write_text(s.replace(old, new), encoding="utf-8")
sub("app/agents/base.py", '''        finding = {"headline": headline, "details": details, "numbers": self.numbers(r), "source": source}
        ctx.findings[self.name] = finding''', '''        headline, details = self.tidy(r, headline, list(details))
        finding = {"headline": headline, "details": details, "numbers": self.numbers(r), "source": source}
        ctx.findings[self.name] = finding''')
sub("app/agents/base.py", '''    def template(self, r: dict) -> tuple[str, list[str]]:''', '''    def tidy(self, r: dict, headline: str, details: list[str]) -> tuple[str, list[str]]:
        """Lines the code owns or checks after the model wrote them (default: as written)."""
        return headline, details

    def template(self, r: dict) -> tuple[str, list[str]]:''')
sub("app/agents/longevity.py", '''    def template(self, r: dict) -> tuple[str, list[str]]:''', '''    def tidy(self, r: dict, headline: str, details: list[str]) -> tuple[str, list[str]]:
        """One horizon, said once, built in code ("to age 95", or "until your partner is 94"); no sentence that names an
        age past 100 or a second horizon for a partner."""
        import re
        head = f"Plan for your money to last {r.get('horizon_text') or 'to age ' + str(r['horizon_age'])}."

        def odd(s: str) -> bool:
            return bool(re.search(r"partner'?s plan|plan for your partner|\b(?:1\d\d)\b", s)) or "1 in 4" in s
        return head, [d for d in details if not odd(d)][:3]

    def template(self, r: dict) -> tuple[str, list[str]]:''')
sub("app/agents/longevity.py", '''say it as your partner's age (partner_age_at_horizon), never as your own age past 100.")''',
    '''say it as your partner's age (partner_age_at_horizon), never as your own age past 100. Give one horizon only, never a "
                    "second one for a partner, and never name an age past 100.")''')
print("ok")
