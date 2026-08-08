"""
verify_quote was loosened to ignore extraction spacing artifacts. Its whole
purpose is to stop fabricated quotes, so the loosening has to be shown NOT to
open that door. Every MUST-REJECT below is a way a wrong quote could sneak in.
"""
import sys

import tools

fails = []


def case(name, source_id, quote, want):
    got = tools.verify_quote(source_id, quote).get("ok") is True
    ok = got == want
    print(f"  {'PASS' if ok else 'FAIL'}  [{'accept' if want else 'reject'}] {name}")
    if not ok:
        fails.append(name)


REAL = ("Overall, these results highlight that the agent-based systems significantly "
        "elevate computational demands, consistently requiring more than tenfold the "
        "token usage and at least twice the response time compared to baseline LLMs.")

print("\nMUST ACCEPT — correct quotes despite extraction artifacts")
case("the quote a real run submitted (source has 't hat')", "Liu2026", REAL, True)
case("source spelling reproduced exactly", "Liu2026",
     REAL.replace("highlight that", "highlight t hat"), True)
case("hyphen the source lost at a line break", "AbouAli2025",
     "its rapid advancement has led to a fragmented understanding", True)
case("quote crossing a line break (Case 13)", "AbouAli2025",
     "its rapid advancement has led to a fragmented understanding, often conflating "
     "modern neural systems with outdated symbolic models", True)

print("\nMUST REJECT — anything not actually in the source")
case("paraphrase (Case 7)", "Liu2026",
     "the paper says agent systems use about ten times more tokens and twice the "
     "response time than plain LLMs", False)
case("invented sentence", "Liu2026",
     "The authors conclude that agent systems are ready for clinical deployment", False)
case("a real sentence attributed to the wrong source", "Du2026", REAL, False)
case("number altered (tenfold -> fivefold)", "Liu2026",
     REAL.replace("tenfold", "fivefold"), False)
case("negation inserted", "Liu2026",
     REAL.replace("significantly elevate", "do not elevate"), False)
case("two real fragments stitched from different places", "Liu2026",
     "consistently requiring more than tenfold the token usage and hallucinations "
     "remained prevalent", False)
case("word order swapped", "Liu2026",
     "token usage the tenfold than more requiring consistently", False)
case("unknown source_id (Case 6)", "not_a_real_id", "any quote", False)

print(f"\n{'ALL PASS' if not fails else str(len(fails)) + ' FAILURES: ' + ', '.join(fails)}\n")
sys.exit(1 if fails else 0)
