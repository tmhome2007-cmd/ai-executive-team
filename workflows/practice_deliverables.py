"""Small representative contract checks, not a universal AI truth evaluator."""

import re
from workflows.business_revision_contract import validate_sample


def validate_deliverable(raw, specification):
    if not specification or not specification["structured"]:
        return raw
    spec = specification["specification"]
    scope = spec["exercise"] + "\nSupplied facts: " + spec["supplied_facts"]
    sample = validate_sample(raw, scope, preserve_unknowns=True)
    for sentence in re.split(r"[.!?\n]", sample):
        if re.search(
            r"\bI (?:have )?(?:sent|emailed|contacted|published|executed)\b",
            sentence,
            re.I,
        ) and not re.search(r"\b(?:not|no|never|cannot)\b", sentence, re.I):
            raise ValueError(
                "Private text practice cannot claim external actions were performed"
            )
    kind = spec["deliverable_kind"]
    lower = sample.lower()
    if len(sample) < 100 or re.fullmatch(r"\s*[{\[].*[}\]]\s*", sample, re.S):
        raise ValueError(
            "Produce the actual requested text deliverable, not JSON instructions or a title"
        )
    if kind == "guide":
        # The observed failure repeated "use the create function" without help.
        steps = re.findall(r"(?m)^\s*\d+[.)]\s+(.+)", sample)
        if len(steps) < 3 or any(len(step.split()) < 8 for step in steps[:3]):
            raise ValueError(
                "Guide needs three useful numbered steps with concrete detail, not repeated function names"
            )
        if "task" in scope.lower() and not re.search(
            r"\b(?:example|fictional|e\.g\.)\b", sample, re.I
        ):
            raise ValueError(
                "Use a clearly fictional task example to make the sequence understandable"
            )
        if re.search(r"interface.*(?:unknown|unspecified)", scope, re.I):
            for line in sample.splitlines():
                click = re.search(r"\b(?:click|tap|press)\b", line, re.I)
                invented_view = re.search(
                    r"\b(?:task list|list of tasks|task menu|task screen|task page|dashboard)\b",
                    line,
                    re.I,
                ) and re.search(
                    r"\b(?:select|choose|find|open|view|navigate|display|shown|appears)\b",
                    line,
                    re.I,
                )
                invented_field = re.search(
                    r"\b(?:button|icon|tab|field)\b", line, re.I
                ) and (
                    re.match(r"\s*\d+[.)]", line)
                    or re.search(
                        r"\b(?:use|enter\w*|fill\w*|type|select)\b", line, re.I
                    )
                )
                action = click or invented_view or invented_field
                if action and not re.search(r"\b(?:do not|cannot|never)\b", line, re.I):
                    raise ValueError(
                        "Unknown interface controls cannot become instructions using invented controls, task views or fields"
                    )
        if re.search(
            r"interface.*(?:unknown|unspecified)", scope, re.I
        ) and not re.search(
            r"(?:interface|controls|buttons).*?(?:unknown|unspecified|not specified)",
            sample,
            re.I,
        ):
            raise ValueError("Guide must label unknown interface controls explicitly")
    elif kind == "evidence_summary":
        if re.search(r"\b14(?:[- ]day| days)\b", sample, re.I) and not re.search(
            r"\b14(?:[- ]day| days)\b", spec["supplied_facts"], re.I
        ):
            raise ValueError(
                "Do not import an unrelated 14-day policy into the supplied evidence summary"
            )
        if any(
            heading not in lower for heading in ("findings", "unknowns", "next action")
        ):
            raise ValueError(
                "Evidence summary needs Findings, Unknowns and Next Action"
            )
        if "five checks" in scope.lower() and not (
            re.search(r"\b(?:five|5)\b", lower)
            and re.search(r"\b(?:four|4)\b", lower)
            and "reminder" in lower
        ):
            raise ValueError(
                "Preserve the supplied expected and passed test counts and reminder failure"
            )
        if not re.search(r"cause.{0,70}(?:unknown|not (?:known|established))", lower):
            raise ValueError("Keep the failure cause explicitly unknown")
        if not re.search(
            r"\b(?:request|obtain|ask|collect)\b.{0,100}(?:reproduction|due time|steps)",
            lower,
        ):
            raise ValueError("Request missing reproduction evidence before a new test")
    elif kind == "reply":
        if re.search(
            r"\[\s*(?:your name|customer name|company name|signature)\s*\]",
            sample,
            re.I,
        ):
            raise ValueError(
                "Return a complete private reply without signing or identity placeholders"
            )
        if "14 days" in scope.lower() and not re.search(
            r"\b14(?:[- ]day| days)\b", lower
        ):
            raise ValueError("Preserve the supplied 14-day policy")
        # A duration alone does not establish whether purchase, delivery or receipt starts it.
        period_anchor = r"\b14(?:[- ]day| days)\s+(?:of|after|from|following|since)\s+(?:the\s+|your\s+)?(purchase|delivery|receipt|order)\b"
        supplied_anchors = set(re.findall(period_anchor, scope, re.I))
        for anchor in re.findall(period_anchor, sample, re.I):
            if anchor.casefold() not in {
                value.casefold() for value in supplied_anchors
            }:
                raise ValueError(
                    "Do not invent when the supplied 14-day return period starts; preserve its wording and label the start event unknown"
                )
        start_unspecified = re.search(
            r"event starting the 14.day period is (?:unspecified|unknown)",
            spec["supplied_facts"],
            re.I,
        )
        if start_unspecified:
            if not re.search(
                r"(?:start(?:ing)? (?:event|point|date)|(?:event|point|date) (?:that )?starts|when .{0,30}(?:period|days) (?:starts|begins))"
                r".{0,100}(?:unknown|unspecified|not specified|not known)",
                sample,
                re.I,
            ):
                raise ValueError(
                    "Explicitly state that the event starting the 14-day period is unspecified"
                )
            if re.search(
                r"(?:purchase date|delivery date|receipt).{0,160}(?:period has started|period starts|period begins)",
                sample,
                re.I,
            ):
                raise ValueError(
                    "A purchase or delivery date cannot establish an unspecified period start"
                )
        if "unused" in scope.lower() and "unused" not in lower:
            raise ValueError("Preserve the unused-item policy condition")
        if not (
            "purchase date" in lower and ("condition" in lower or "unused" in lower)
        ):
            raise ValueError("Ask for the missing purchase date and item condition")
        if re.search(
            r"no refund has been approved or issued", spec["supplied_facts"], re.I
        ) and not re.search(
            r"\bno refund\b.{0,50}\bapproved\b.{0,25}\bissued\b"
            r"|\brefund\b.{0,30}\bnot\b.{0,30}\bapproved\b.{0,25}\bissued\b",
            sample,
            re.I,
        ):
            raise ValueError(
                "Preserve the supplied fact: no refund has been approved or issued"
            )
        for line in re.split(r"[.!?\n]", sample):
            if re.search(
                r"\b(?:refund|return)\b.{0,40}\b(?:approved|issued|processed|guaranteed)\b|\b(?:will|shall)\b.{0,40}\brefund\b",
                line,
                re.I,
            ) and not re.search(
                r"\b(?:not|no|cannot|can’t|can.not|without)\b", line, re.I
            ):
                raise ValueError(
                    "A private draft cannot promise or claim a refund or approval"
                )
    return sample
