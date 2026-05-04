#!/usr/bin/env python3
"""
BIL v0.7 Interpreter
====================

SUES = Semantic Unit Encoding Syntax
BIL  = Biophonic Intermediary Language

Purpose:
    Convert controlled English or SUES slot strings into:
      English -> SUES terms -> SUES slots -> BIL-IR -> BIL tokens -> English

Pipeline:
    human_input  → normalize
                 → SUES terms (word-sense disambiguation)
                 → SUES slot frame
                 → BIL-IR (structured JSON)
                 → BIL token stream
                 → natural language output

Core rule:
    WRONG  →  word = token
    CORRECT →  word sense = semantic concept = BIL token path

Run:
    python3 bil_v07_interpreter.py

CLI:
    python3 bil_v07_interpreter.py --english "Run the program."
    python3 bil_v07_interpreter.py --sues "ACT:!askdo AGT:@self PRED:partmake OBJ:BIL.partnet STYLE:stepclear+technical OUT:codeout"
    python3 bil_v07_interpreter.py --english "Run the program." --json
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


# =============================================================================
# ① SUES → BIL concept map
# =============================================================================

SUES_MAP: Dict[str, str] = {
    # Entities / particles
    "@self": "entity.person.speaker",
    "@you": "entity.person.addressee",
    "@we": "entity.group.speaker_inclusive",
    "@it": "entity.reference.object",
    "@this": "deixis.near.object",
    "@that": "deixis.far.object",

    # Speech acts
    "say": "speech.act.say",
    "?ask": "speech.act.ask_info",
    "!askdo": "speech.act.request_action",
    "!do": "speech.act.command",
    "!risk": "speech.act.warn",
    "whyshow": "speech.act.explain",
    "whatshow": "speech.act.describe",
    "mindgive": "speech.act.teach",

    # Core verbs / states
    "=id": "state.identity.be",
    "=state": "state.condition.be",
    "=loc": "state.location.be_at",
    "own": "state.possession.have",
    "exp": "state.experience.have",
    "do": "action.perform.general",
    "toolwith": "action.use.instrument",
    "receive": "action.transfer.receive",
    "grabown": "action.transfer.take",
    "place": "action.place.put",
    "holdstay": "action.possession.keep",

    # Desire / choice
    "want": "state.desire.want",
    "musthave": "state.necessity.need",
    "rankwant": "state.preference.prefer",
    "pick": "action.decision.choose",
    "picklock": "action.decision.commit",
    "let": "action.permission.allow",
    "letnot": "action.permission.deny",

    # Create family
    "make": "action.create.general",
    "newmake": "action.create.novel",
    "partmake": "action.create.assemble",
    "sysmake": "action.create.process_output",
    "yieldmake": "action.create.material_output",
    "planmake": "action.create.plan_structure",
    "firstmake": "action.create.invent",
    "growmake": "action.create.iterative_growth",

    # Improve / repair
    "bettermake": "action.change.improve",
    "workagain": "action.repair.restore_function",
    "damageheal": "action.repair.damage",
    "bestfit": "action.improve.optimize",
    "clearmake": "action.improve.refine",
    "moregood": "action.improve.enhance",
    "breaknot": "action.improve.harden",
    "tierup": "action.improve.upgrade",

    # Cognition
    "know": "state.knowledge.possess",
    "minddo": "action.cognition.think",
    "truehold": "state.cognition.believe",
    "structknow": "state.cognition.understand",
    "getknow": "action.cognition.learn",
    "backknow": "action.cognition.remember",
    "clueknow": "action.cognition.infer",
    "temptrue": "state.cognition.assume",

    # Truth / modality
    "=true": "logic.truth.true",
    "=false": "logic.truth.false",
    "~maybe": "modality.certainty.possible",
    "~likely": "modality.certainty.probable",
    "=sure": "modality.certainty.high",
    "able": "modality.ability.can",
    "softmust": "modality.recommend.should",
    "hardmust": "modality.necessity.must",

    # Time
    "<time": "time.tense.past",
    "=time": "time.tense.present",
    ">time": "time.tense.future",
    "now": "time.deictic.now",
    "near>": "time.future.near",
    "far>": "time.future.later",
    "<before": "time.relation.before",
    ">after": "time.relation.after",
    "inwhile": "time.relation.during",

    # Motion / system operation
    "go": "action.motion.go",
    "come": "action.motion.come",
    "locchange": "action.motion.move",
    "stepgo": "action.motion.walk",
    "faststep": "action.motion.run_foot",
    "airgo": "action.motion.fly",
    "vehgo": "action.motion.drive_vehicle",
    "causego": "action.transfer.send",
    "ownmove": "action.transfer.give",
    "getfrom": "action.transfer.receive",
    "sysdo": "action.system.operate",
    "liquidgo": "action.fluid.flow",
    "officewant": "action.social.campaign_for_office",

    # Perception
    "eyeknow": "action.perceive.see",
    "eyeaim": "action.perceive.look",
    "eyetime": "action.perceive.watch",
    "earknow": "action.perceive.hear",
    "earaim": "action.perceive.listen",
    "bodyknow": "action.perceive.feel",
    "tongueknow": "action.perceive.taste",
    "noseknow": "action.perceive.smell",

    # Value / quality
    "+value": "quality.value.good",
    "-value": "quality.value.bad",
    "more+": "quality.value.better",
    "max+": "quality.value.best",
    "more-": "quality.value.worse",
    "max-": "quality.value.worst",
    "size+": "quality.size.big",
    "size-": "quality.size.small",
    "speed+": "quality.speed.fast",
    "speed-": "quality.speed.slow",
    "ambig-": "quality.clarity.clear",
    "ambig+": "quality.clarity.vague",

    # Risk / defense
    "harmmay": "state.risk.danger",
    "badmaybe": "state.risk.uncertain_harm",
    "harmagent": "entity.risk.threat",
    "huntagent": "entity.risk.predator",
    "harmblock": "action.defense.protect",
    "attackblock": "action.defense.resist_attack",
    "safemake": "action.defense.secure",
    "riskleave": "action.defense.escape",
    "contactnot": "action.avoid.prevent_contact",

    # Social / roles
    "@person": "entity.person.general",
    "@goodrel": "entity.person.friend",
    "@badrel": "entity.person.enemy",
    "@teachrole": "entity.role.teacher",
    "@learnrole": "entity.role.student",
    "@mgr": "entity.role.manager",
    "@emp": "entity.role.employee",
    "@buyerrole": "entity.role.customer",
    "@many": "entity.group.general",

    # Tech / AI
    "partnet": "object.structure.system",
    "BIL.partnet": "object.structure.system",
    "codedo": "object.software.program",
    "symdo": "object.software.code",
    "stepdo": "object.procedure.algorithm",
    "infobits": "object.information.data",
    "mapmind": "object.representation.model",
    "@aimind": "entity.system.ai",
    "symunit": "object.symbol.token",
    "splitmeaning": "action.language.parse",
    "langmove": "action.language.translate",
    "meanread": "action.meaning.interpret",
    "meaning2sym": "action.representation.encode",
    "sym2meaning": "action.representation.decode",
    "checktrue": "action.validation.validate",
    "buildcode": "action.software.compile",

    # Work / task
    "taskdo": "action.work.general",
    "paidrole": "entity.role.job",
    "doitem": "object.task.unit",
    "taskgroup": "object.task.project",
    "futuremap": "object.plan.general",
    "timemap": "object.plan.schedule",
    "peopletime": "event.work.meeting",
    "skillteach": "action.work.train",
    "assistdo": "action.social.help",
    "donebecome": "action.task.finish",
    "begin": "action.task.start",
    "keepdo": "action.task.continue",
    "enddo": "action.task.stop",
    "ranktask": "quality.task.priority",
    "nowneed": "quality.task.urgent",

    # Extended entries (from test cases)
    "buyplace": "location.commerce.store",
    "yesallow": "action.permission.approve",
    "moneyborrow": "object.finance.loan",
    "bodyrest_seat": "action.body.sit",
    "waterpath": "object.geography.river",
    "paramgive": "action.configure.set_parameter",
    "seeenergy": "object.energy.light",
    "weight-": "quality.weight.light",
    "firestart": "action.fire.ignite",
    "moneyhouse": "finance.institution.bank",
    "riveredge": "geography.land.riverbank",

    # Output / style
    "shortclear": "style.length.concise",
    "deepclear": "style.detail.detailed",
    "easyclear": "style.complexity.simple",
    "expertclear": "style.register.technical",
    "technical": "style.register.technical",
    "workpolite": "style.register.professional",
    "warmtone": "style.tone.friendly",
    "flattone": "style.tone.neutral",
    "hightone": "style.register.formal",
    "lowtone": "style.register.casual",
    "stepclear": "style.structure.step_by_step",
    "checklist": "output.format.checklist",
    "sayscript": "output.format.script",
    "codeout": "output.format.code",
    "jsonout": "output.format.json",
    "pdfout": "output.format.pdf",
    "answer": "output.format.answer",
}


# =============================================================================
# ② Concept → BIL token registry
# =============================================================================

TOKEN_REGISTRY: Dict[str, str] = {
    # Speech acts
    "speech.act.say": "W1 C1 R1",
    "speech.act.ask_info": "G1 W1 R2",
    "speech.act.request_action": "G2 W1 R2",
    "speech.act.command": "G2 R3 W2",
    "speech.act.warn": "R3 G2 W1",
    "speech.act.explain": "W2 C1 W3",
    "speech.act.describe": "W2 C1 R2",
    "speech.act.teach": "W3 C1 R2",

    # Entities
    "entity.person.speaker": "R1 W1",
    "entity.person.addressee": "R1 W2",
    "entity.group.speaker_inclusive": "R2 W1",
    "entity.reference.object": "R2 W2",
    "entity.person.general": "R2 R1 W1",
    "entity.person.friend": "R2 R1",
    "entity.person.enemy": "R3 R1",
    "entity.role.teacher": "R2 W3 W1",
    "entity.role.student": "R2 W1 W3",
    "entity.role.manager": "R2 W3 R3",
    "entity.role.employee": "R2 W1 R3",
    "entity.role.customer": "R2 W2 R1",
    "entity.group.general": "R2 R2",

    # Desire / action / state
    "state.desire.want": "R2 W1 G1",
    "state.necessity.need": "R3 W1 G2",
    "state.preference.prefer": "R2 W2 G1",
    "action.decision.choose": "W2 R2 G2",
    "action.decision.commit": "W3 R2 G2",
    "action.permission.allow": "W1 G1 R2",
    "action.permission.deny": "R3 G1 R2",
    "action.permission.approve": "W3 PERM YES",

    # Create family
    "action.create.general": "W1 R1 W1",
    "action.create.novel": "W1 R1 W3",
    "action.create.assemble": "W1 R2 W2",
    "action.create.process_output": "W1 W3 R2",
    "action.create.material_output": "W2 R1 W3",
    "action.create.plan_structure": "W3 R1 W2",
    "action.create.invent": "W3 W1 R2",
    "action.create.iterative_growth": "W2 W3 R1",

    # Improve / repair
    "action.change.improve": "W2 W1 R2",
    "action.repair.restore_function": "W2 R3 R1",
    "action.repair.damage": "W2 R3 R2",
    "action.improve.optimize": "W3 W2 R1",
    "action.improve.refine": "W3 R2 R1",
    "action.improve.enhance": "W2 W3 R2",
    "action.improve.harden": "R3 W2 W3",
    "action.improve.upgrade": "W3 R3 W1",

    # Cognition
    "state.knowledge.possess": "R2 W3 W1",
    "action.cognition.think": "W1 W2 R2",
    "state.cognition.believe": "R2 W2 W3",
    "state.cognition.understand": "R2 W3 R1",
    "state.cognition.understand_informal": "R2 V3",
    "action.cognition.learn": "W1 R2 W3",
    "action.cognition.remember": "W2 R2 W3",
    "action.cognition.infer": "W3 R1 R2",
    "state.cognition.assume": "R2 R3 W3",

    # Motion / system
    "action.motion.go": "W2 R1",
    "action.motion.come": "W2 R2",
    "action.motion.move": "W2 W1 R1",
    "action.motion.walk": "W2 R1 R2",
    "action.motion.run_foot": "W2 W3 R1",
    "action.motion.fly": "W2 W3 G1",
    "action.motion.drive_vehicle": "W2 R3 G1",
    "action.system.operate": "W2 C1 R2",
    "action.fluid.flow": "W2 R1 G1",
    "action.social.campaign_for_office": "W2 R3 G2",

    # Objects / domains
    "object.structure.system": "R2 C1 W3",
    "object.software.program": "R2 C1 W1",
    "object.software.code": "R2 C1 R1",
    "object.procedure.algorithm": "R2 C1 W2",
    "object.information.data": "R1 C1 W3",
    "object.representation.model": "R1 C1 W2",
    "entity.system.ai": "R2 W3 C1",
    "object.symbol.token": "R1 C2 W1",
    "object.finance.loan": "R2 F LOAN",
    "finance.institution.bank": "R2 F1 B1",
    "geography.land.riverbank": "R1 G1 B1",
    "location.commerce.store": "R2 LOC STORE",
    "object.geography.river": "R2 GEO RIVER",
    "object.energy.light": "R1 L1 W3",
    "quality.weight.light": "W3 L1 R1",

    # Extended actions
    "action.body.sit": "W2 B1 R1",
    "action.configure.set_parameter": "W3 R2 C1",
    "action.fire.ignite": "W1 L1 R3",

    # Problem / solution
    "state.problem.failure": "R3 PR5",
    "state.problem.error": "R3 PR3",
    "state.software.bug": "R3 PR4",
    "object.solution.general": "W3 PR1",

    # Quality / style
    "quality.value.good": "W3 R1",
    "quality.value.bad": "R3 W1",
    "quality.value.better": "W3 R1 W3",
    "quality.value.best": "W3 W3 R1",
    "style.length.concise": "ST1",
    "style.detail.detailed": "ST2",
    "style.complexity.simple": "ST3",
    "style.register.technical": "ST4",
    "style.register.professional": "ST5",
    "style.tone.friendly": "ST6",
    "style.tone.neutral": "ST7",
    "style.register.formal": "ST8",
    "style.register.casual": "ST9",
    "style.structure.step_by_step": "ST10",
    "output.format.checklist": "OUT1",
    "output.format.script": "OUT2",
    "output.format.code": "OUT3",
    "output.format.json": "OUT4",
    "output.format.pdf": "OUT5",
    "output.format.answer": "OUT0",

    # Modality / time
    "time.tense.future": "W3",
    "time.tense.past": "R1 R1",
    "modality.certainty.probable": "W3 G1 R2",
    "modality.certainty.possible": "G1 R2 W3",
    "modality.certainty.high": "W3 W3 G2",
}


# =============================================================================
# ③ English surface → SUES lexicon
# =============================================================================

ENGLISH_TO_SUES: Dict[str, str] = {
    # Pronouns
    "i": "@self", "me": "@self", "my": "@self",
    "you": "@you", "we": "@we", "it": "@it",
    "this": "@this", "that": "@that",

    # Prompt / speech-act trigger words
    "please": "!askdo",
    "explain": "whyshow",
    "describe": "whatshow",
    "tell": "tell",
    "ask": "?ask",
    "warn": "!risk",
    "summarize": "shortmean",
    "continue": "keepgo",
    "compare": "diffshow",
    "rank": "orderbest",

    # Core verbs
    "want": "want",
    "need": "musthave",
    "prefer": "rankwant",
    "choose": "pick",
    "decide": "picklock",
    "make": "make",
    "create": "newmake",
    "build": "partmake",
    "generate": "sysmake",
    "produce": "yieldmake",
    "improve": "bettermake",
    "fix": "workagain",
    "repair": "damageheal",
    "optimize": "bestfit",
    "refine": "clearmake",
    "harden": "breaknot",
    "use": "toolwith",
    "get": "receive",
    "take": "grabown",
    "put": "place",
    "keep": "holdstay",
    "approve": "yesallow",
    "approved": "yesallow",
    "approves": "yesallow",
    "sit": "bodyrest_seat",
    "sitting": "bodyrest_seat",
    "sat": "bodyrest_seat",
    "sets": "paramgive",
    "built": "partmake",
    "fixed": "workagain",

    # Common nouns → SUES objects
    "system": "partnet",
    "program": "codedo",
    "software": "codedo",
    "code": "symdo",
    "algorithm": "stepdo",
    "data": "infobits",
    "model": "mapmind",
    "file": "@file",
    "document": "@doc",
    "message": "@msg",
    "question": "@question",
    "answer": "@answer",
    "store": "buyplace",
    "loan": "moneyborrow",
    "river": "waterpath",
    "value": "paramgive",

    # Style / output modifiers
    "concise": "shortclear",
    "detailed": "deepclear",
    "simple": "easyclear",
    "technical": "technical",
    "professional": "workpolite",
    "friendly": "warmtone",
    "formal": "hightone",
    "casual": "lowtone",
    "stepwise": "stepclear",
    "step": "stepclear",
    "pdf": "pdfout",
    "json": "jsonout",
}

STOPWORDS = {
    "the", "a", "an", "to", "of", "and", "or", "in", "on", "for", "with",
    "by", "at", "from", "as", "into", "about", "is", "are", "am", "was",
    "were", "be", "being", "been", "do", "does", "did", "will", "would",
    "can", "could", "should", "may", "might",
}


# =============================================================================
# ④ Ambiguity resolver
# =============================================================================

# Each key is an ambiguous English word.
# Each value maps sues-term → list of context clue words that favour that sense.
AMBIGUOUS: Dict[str, Dict[str, List[str]]] = {
    "run": {
        "faststep": ["person", "legs", "store", "road", "race", "quickly"],
        "sysdo":    ["program", "code", "script", "server", "command", "workflow", "software"],
        "liquidgo": ["water", "river", "pipe", "fluid", "leak"],
        "officewant": ["office", "election", "candidate", "campaign"],
    },
    "bank": {
        "moneyhouse": ["money", "loan", "account", "deposit", "credit", "approved"],
        "riveredge":  ["river", "water", "shore", "creek", "stream"],
    },
    "light": {
        "seeenergy": ["bright", "lamp", "sun", "shine", "visible", "dark"],
        "weight-":   ["heavy", "weight", "carry", "mass"],
        "firestart": ["fire", "candle", "match", "burn", "ignite"],
    },
    "set": {
        "putloc":    ["table", "down", "place", "object"],
        "paramgive": ["value", "setting", "parameter", "config", "variable"],
        "manygroup": ["collection", "group", "math", "items"],
        "hardbecome": ["concrete", "gel", "harden", "freeze"],
    },
    "charge": {
        "payask":    ["fee", "price", "money", "bill", "card"],
        "elecstate": ["electric", "battery", "electron", "voltage"],
        "attackgo":  ["attack", "forward", "rush"],
        "lawblame":  ["accuse", "court", "crime", "law"],
    },
}


def resolve_ambiguous_word(word: str, context_words: List[str]) -> Dict[str, Any]:
    """Score each candidate sense by clue overlap with context_words."""
    if word not in AMBIGUOUS:
        return {
            "word": word,
            "ambiguous": False,
            "chosen_sues": None,
            "confidence": 1.0,
            "reason": "not ambiguous",
        }

    scores: Dict[str, Dict[str, Any]] = {}
    for sues_term, clues in AMBIGUOUS[word].items():
        matched = [c for c in clues if c in context_words]
        scores[sues_term] = {"score": len(matched), "matched": matched}

    best = max(scores, key=lambda k: scores[k]["score"])
    best_score = scores[best]["score"]

    if best_score == 0:
        return {
            "word": word,
            "ambiguous": True,
            "chosen_sues": None,
            "confidence": 0.0,
            "reason": "no context clue matched",
            "candidates": list(AMBIGUOUS[word].keys()),
            "scores": scores,
        }

    total = sum(v["score"] for v in scores.values()) or 1
    return {
        "word": word,
        "ambiguous": True,
        "chosen_sues": best,
        "confidence": round(best_score / total, 2),
        "reason": f"matched clues: {scores[best]['matched']}",
        "scores": scores,
    }


# =============================================================================
# ⑤ BIL-IR dataclasses
# =============================================================================

@dataclass
class BILSource:
    speaker: str = "entity.person.speaker"
    signature: Optional[str] = None


@dataclass
class BILSemanticFrame:
    agent: Optional[str] = None
    predicate: Optional[str] = None
    patient: Optional[str] = None
    object: Optional[Any] = None
    target: Optional[str] = None
    location: Optional[str] = None
    time: Optional[str] = None
    cause: Optional[str] = None
    negated: bool = False
    modifiers: List[str] = field(default_factory=list)


@dataclass
class BILModality:
    certainty: float = 0.85
    urgency: float = 0.5
    evidentiality: str = "direct"
    emotion: str = "neutral"


@dataclass
class BILConstraints:
    avoid: List[str] = field(default_factory=lambda: ["ambiguity", "fabrication"])
    prefer: List[str] = field(default_factory=list)


@dataclass
class BILOutputGoal:
    format: str = "answer"
    language: str = "English"
    length: str = "medium"
    style: List[str] = field(default_factory=list)


@dataclass
class BILMessage:
    bil_version: str = "0.7"
    message_id: str = "msg_auto"
    thread_id: str = "thread_default"
    source: BILSource = field(default_factory=BILSource)
    speech_act: str = "speech.act.say"
    domain: str = "general"
    intent: str = "auto_interpret"
    semantic_frame: BILSemanticFrame = field(default_factory=BILSemanticFrame)
    modality: BILModality = field(default_factory=BILModality)
    constraints: BILConstraints = field(default_factory=BILConstraints)
    output_goal: BILOutputGoal = field(default_factory=BILOutputGoal)
    source_text: Optional[str] = None
    parse_debug: Dict[str, Any] = field(default_factory=dict)
    ambiguity_report: List[Dict[str, Any]] = field(default_factory=list)


# =============================================================================
# ⑥ Normalization and SUES slot parsing
# =============================================================================

def normalize_english(text: str) -> List[str]:
    clean = text.lower()
    clean = re.sub(r"[^a-z0-9_@.!?+\-]+", " ", clean)
    clean = clean.replace(".", " ").replace("?", " ").replace("!", " ")
    return [w for w in clean.split() if w]


def map_sues_term(term: str) -> str:
    return SUES_MAP.get(term, term)


def parse_sues_slots(sues: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for chunk in sues.split():
        if ":" not in chunk:
            continue
        key, raw_value = chunk.split(":", 1)
        values = [v for v in raw_value.split("+") if v]
        mapped = [map_sues_term(v) for v in values]
        result[key.upper()] = mapped[0] if len(mapped) == 1 else mapped
    return result


def sues_to_bil_ir(sues: str, thread_id: str = "thread_default") -> Dict[str, Any]:
    slots = parse_sues_slots(sues)

    msg = BILMessage(thread_id=thread_id)
    msg.source.speaker = slots.get("AGT", "entity.person.speaker")
    msg.speech_act = slots.get("ACT", "speech.act.say")

    f = msg.semantic_frame
    f.agent     = slots.get("AGT", "entity.person.speaker")
    f.predicate = slots.get("PRED")
    f.patient   = slots.get("PAT")
    f.object    = slots.get("OBJ")
    f.target    = slots.get("TGT")
    f.location  = slots.get("LOC")
    f.time      = slots.get("TIME")
    f.cause     = slots.get("CAUSE")

    style = slots.get("STYLE")
    if style:
        msg.output_goal.style = style if isinstance(style, list) else [style]

    out = slots.get("OUT")
    if out:
        raw = str(out)
        msg.output_goal.format = raw.split(".")[-1] if raw.startswith("output.format.") else raw

    return asdict(msg)


# =============================================================================
# ⑦ English → SUES → BIL-IR
# =============================================================================

# Maps SUES terms to which sentence slot they most likely fill.
SUES_TO_ROLE_HINT: Dict[str, str] = {
    "@self": "AGT", "@you": "AGT", "@we": "AGT",
    "!askdo": "ACT", "!do": "ACT", "?ask": "ACT",
    "whyshow": "ACT", "whatshow": "ACT", "say": "ACT",

    "want": "PRED", "musthave": "PRED",
    "partmake": "PRED", "bettermake": "PRED",
    "workagain": "PRED", "damageheal": "PRED",
    "bestfit": "PRED", "sysdo": "PRED",
    "faststep": "PRED", "liquidgo": "PRED",
    "bodyrest_seat": "PRED", "paramgive": "PRED",
    "yesallow": "PRED",

    "partnet": "OBJ", "codedo": "OBJ", "symdo": "OBJ",
    "infobits": "OBJ", "mapmind": "OBJ",
    "buyplace": "OBJ", "moneyborrow": "OBJ",
    "waterpath": "OBJ", "riveredge": "OBJ",
    "moneyhouse": "OBJ", "seeenergy": "OBJ",
    "weight-": "OBJ",

    "shortclear": "STYLE", "deepclear": "STYLE",
    "easyclear": "STYLE", "expertclear": "STYLE",
    "technical": "STYLE", "workpolite": "STYLE",
    "stepclear": "STYLE",
}


def english_to_sues_terms(text: str) -> Dict[str, Any]:
    words = normalize_english(text)
    content_words = [w for w in words if w not in STOPWORDS]

    ambiguity_report: List[Dict[str, Any]] = []
    sues_terms: List[str] = []

    for word in content_words:
        if word in AMBIGUOUS:
            resolved = resolve_ambiguous_word(word, content_words)
            ambiguity_report.append(resolved)
            sues_terms.append(resolved["chosen_sues"] or f"AMBIG[{word}]")
            continue
        mapped = ENGLISH_TO_SUES.get(word)
        sues_terms.append(mapped if mapped else f"UNK[{word}]")

    return {
        "input": text,
        "words": words,
        "content_words": content_words,
        "sues_terms": sues_terms,
        "ambiguity_report": ambiguity_report,
    }


def sues_terms_to_slots(sues_terms: List[str]) -> str:
    slots: Dict[str, Any] = {
        "ACT": None, "AGT": None, "PRED": None, "OBJ": None, "STYLE": [],
    }
    extra_predicates: List[str] = []

    for term in sues_terms:
        if term.startswith("UNK[") or term.startswith("AMBIG["):
            continue
        role = SUES_TO_ROLE_HINT.get(term)
        if role == "STYLE":
            slots["STYLE"].append(term)
        elif role == "PRED" and slots["PRED"] is not None:
            extra_predicates.append(term)
        elif role and slots.get(role) is None:
            slots[role] = term
        elif role == "OBJ" and slots.get("OBJ") is not None:
            slots.setdefault("TGT", term)

    slots["ACT"] = slots["ACT"] or "!do"
    slots["AGT"] = slots["AGT"] or ("@you" if slots["ACT"] == "!do" else "@self")

    if extra_predicates:
        slots["STYLE"].append("stepclear")

    chunks = [f"{k}:{slots[k]}" for k in ["ACT", "AGT", "PRED", "OBJ", "TGT"] if slots.get(k)]
    if slots["STYLE"]:
        chunks.append("STYLE:" + "+".join(slots["STYLE"]))
    return " ".join(chunks)


def english_to_bil_ir(text: str, thread_id: str = "thread_default") -> Dict[str, Any]:
    parsed = english_to_sues_terms(text)
    sues_slot_string = sues_terms_to_slots(parsed["sues_terms"])
    bil_ir = sues_to_bil_ir(sues_slot_string, thread_id=thread_id)
    bil_ir["source_text"] = text
    bil_ir["parse_debug"] = {
        "words": parsed["words"],
        "content_words": parsed["content_words"],
        "sues_terms": parsed["sues_terms"],
        "sues_slot_string": sues_slot_string,
        "ambiguity_report": parsed["ambiguity_report"],
    }
    bil_ir["ambiguity_report"] = parsed["ambiguity_report"]
    return bil_ir


# =============================================================================
# ⑧ Validation, encoding, generation
# =============================================================================

def validate_bil_ir(bil: Dict[str, Any]) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []

    if not bil.get("speech_act"):
        errors.append("Missing speech_act")

    frame = bil.get("semantic_frame", {})
    if not frame.get("predicate"):
        errors.append("Missing semantic_frame.predicate")
    if not frame.get("agent"):
        warnings.append("Missing semantic_frame.agent")
    if not any(frame.get(s) for s in ["object", "patient", "target"]):
        warnings.append("No object/patient/target specified")

    for item in bil.get("parse_debug", {}).get("sues_terms", []):
        if str(item).startswith("UNK["):
            warnings.append(f"Unknown term: {item}")
        if str(item).startswith("AMBIG["):
            errors.append(f"Unresolved ambiguity: {item}")

    if any(r.get("ambiguous") and not r.get("chosen_sues") for r in bil.get("ambiguity_report", [])):
        errors.append("Unresolved ambiguity present")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


def _tok(concept: Optional[str]) -> str:
    if not concept:
        return ""
    return TOKEN_REGISTRY.get(concept, f"UNK_TOKEN[{concept}]")


def _encode_value(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        t = _tok(value)
        return [t] if t else []
    if isinstance(value, list):
        out: List[str] = []
        for item in value:
            out.extend(_encode_value(item))
        return out
    if isinstance(value, dict):
        out = []
        for v in value.values():
            out.extend(_encode_value(v))
        return out
    return [f"LIT[{value}]"]


def encode_bil_ir(bil: Dict[str, Any]) -> str:
    parts: List[str] = []

    sa = bil.get("speech_act")
    if sa:
        parts.append(_tok(sa))

    frame = bil.get("semantic_frame", {})
    for slot in ["agent", "predicate", "patient", "object", "target", "location", "time", "cause"]:
        parts.extend(_encode_value(frame.get(slot)))

    output = bil.get("output_goal", {})
    parts.extend(_encode_value(output.get("style", [])))

    fmt = output.get("format")
    if fmt:
        concept = fmt if str(fmt).startswith("output.format.") else f"output.format.{fmt}"
        parts.append(_tok(concept))

    parts = [p for p in parts if p]
    return " C1 ".join(parts) + " C2"


_ENGLISH_LABELS: Dict[str, str] = {
    "speech.act.request_action": "please",
    "speech.act.command": "",
    "speech.act.ask_info": "question",
    "speech.act.say": "",
    "speech.act.explain": "explain",
    "entity.person.speaker": "me",
    "entity.person.addressee": "you",
    "entity.group.speaker_inclusive": "we",
    "state.desire.want": "want",
    "state.necessity.need": "need",
    "action.create.assemble": "build",
    "action.change.improve": "improve",
    "action.repair.restore_function": "fix",
    "action.system.operate": "run",
    "action.motion.run_foot": "run",
    "action.fluid.flow": "flow",
    "action.permission.approve": "approve",
    "action.body.sit": "sit",
    "action.configure.set_parameter": "set",
    "object.structure.system": "BIL system",
    "object.software.program": "program",
    "object.software.code": "code",
    "object.information.data": "data",
    "object.representation.model": "model",
    "location.commerce.store": "store",
    "finance.institution.bank": "bank",
    "geography.land.riverbank": "river bank",
    "object.finance.loan": "loan",
    "object.geography.river": "river",
    "quality.weight.light": "lightweight object",
    "object.energy.light": "light",
    "style.structure.step_by_step": "step by step",
    "style.register.technical": "in a technical style",
    "style.length.concise": "concisely",
    "output.format.code": "code",
}


def _label(concept: Optional[str]) -> str:
    if not concept:
        return ""
    return _ENGLISH_LABELS.get(concept, concept)


def generate_english(bil: Dict[str, Any]) -> str:
    frame = bil.get("semantic_frame", {})
    speech_act = bil.get("speech_act")
    output = bil.get("output_goal", {})

    agent_text = _label(frame.get("agent"))
    pred_text  = _label(frame.get("predicate"))
    obj_text   = _label(frame.get("object"))
    tgt_text   = _label(frame.get("target"))

    style_bits = [
        _label(s) for s in output.get("style", [])
        if _label(s) and not _label(s).startswith("style.")
    ]
    style_text = (" " + " ".join(style_bits)) if style_bits else ""

    if speech_act == "speech.act.request_action":
        if pred_text == "want":
            return f"Please help {agent_text} with {obj_text}{style_text}.".strip()
        return f"Please help {agent_text} {pred_text} the {obj_text}{style_text}.".strip()
    if speech_act == "speech.act.command":
        suffix = f" with {tgt_text}" if tgt_text else ""
        return f"{pred_text.capitalize()} the {obj_text}{suffix}{style_text}.".strip()
    if speech_act == "speech.act.explain":
        return f"Explain the {obj_text}{style_text}.".strip()

    parts = [agent_text, pred_text, obj_text, tgt_text]
    return " ".join(p for p in parts if p) + style_text + "."


# =============================================================================
# ⑨ n8n adapter + round-trip driver
# =============================================================================

def n8n_handle(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Webhook-style entry point.

    Payload:
        {
          "thread_id":   "bil-demo",
          "input_type":  "english" | "sues",
          "input_text":  "<string>"
        }
    """
    thread_id  = payload.get("thread_id", "thread_default")
    input_text = payload.get("input_text", "")
    input_type = payload.get("input_type", "english")

    if not input_text:
        return {"ok": False, "thread_id": thread_id, "error": "Missing input_text"}

    if input_type == "sues":
        bil_ir = sues_to_bil_ir(input_text, thread_id=thread_id)
        bil_ir["source_text"] = input_text
    elif input_type == "english":
        bil_ir = english_to_bil_ir(input_text, thread_id=thread_id)
    else:
        return {"ok": False, "thread_id": thread_id, "error": f"Unsupported input_type: {input_type}"}

    validation  = validate_bil_ir(bil_ir)
    bil_tokens  = encode_bil_ir(bil_ir)
    output_text = generate_english(bil_ir)

    return {
        "ok": validation["valid"],
        "thread_id": thread_id,
        "input_type": input_type,
        "input_text": input_text,
        "bil_ir": bil_ir,
        "validation": validation,
        "bil_tokens": bil_tokens,
        "output_text": output_text,
    }


def roundtrip_test(input_text: str) -> Dict[str, Any]:
    return n8n_handle({"thread_id": "roundtrip-test", "input_type": "english", "input_text": input_text})


# =============================================================================
# ⑩ CLI + demo
# =============================================================================

_DEMO_CASES = [
    "Please build the system.",
    "Fix the code.",
    "Run the program.",
    "Run to the store.",
    "The bank approved the loan.",
    "Sit by the river bank.",
    "Set the value to 10.",
    "The light is bright.",
]


def _pretty(result: Dict[str, Any]) -> str:
    lines = [
        f"OK:         {result['ok']}",
        f"INPUT:      {result['input_text']}",
        f"TOKENS:     {result['bil_tokens']}",
        f"OUTPUT:     {result['output_text']}",
        "VALIDATION: " + json.dumps(result["validation"]),
    ]
    amb = result["bil_ir"].get("ambiguity_report", [])
    if amb:
        lines.append("AMBIGUITY:  " + json.dumps(amb, indent=2))
    return "\n".join(lines)


def demo() -> None:
    for case in _DEMO_CASES:
        print("\n" + "=" * 72)
        print(_pretty(roundtrip_test(case)))


def main() -> None:
    ap = argparse.ArgumentParser(description="BIL v0.7 Interpreter")
    ap.add_argument("--english", type=str, help="English input")
    ap.add_argument("--sues",    type=str, help="SUES slot string")
    ap.add_argument("--json",    action="store_true", help="Output raw JSON")
    args = ap.parse_args()

    if args.english or args.sues:
        payload = {
            "thread_id":  "cli",
            "input_type": "sues" if args.sues else "english",
            "input_text": args.sues or args.english,
        }
        result = n8n_handle(payload)
        print(json.dumps(result, indent=2) if args.json else _pretty(result))
        return

    demo()


if __name__ == "__main__":
    main()
