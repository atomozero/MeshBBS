"""
Trivia command for MeshCore BBS.

Quiz game with multiple choice questions, persistent scores,
and leaderboard. Designed for short LoRa messages.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import random
import time
from typing import List, Optional, Dict, Tuple

from sqlalchemy.orm import Session

from .base import BaseCommand, CommandContext, CommandResult, CommandRegistry

# Active questions per user: sender_key -> (question_index, correct_answer, timestamp)
_active_questions: Dict[str, Tuple[int, str, float]] = {}

# Scores stored in memory, persisted via activity log
# sender_key -> {"score": int, "correct": int, "total": int}
_scores: Dict[str, Dict[str, int]] = {}

QUESTION_TIMEOUT = 300  # 5 minutes to answer

# Question bank: (category, question, options_dict, correct_letter)
QUESTIONS = [
    # Radio & Comunicazioni
    ("Radio", "In che anno Marconi fece la prima trasmissione transatlantica?",
     {"A": "1895", "B": "1901", "C": "1912"}, "B"),
    ("Radio", "Cosa significa il codice 73 in CW?",
     {"A": "Arrivederci", "B": "Migliori saluti", "C": "SOS"}, "B"),
    ("Radio", "Quale frequenza usa l'APRS sulla ISS?",
     {"A": "145.825 MHz", "B": "433.500 MHz", "C": "868.000 MHz"}, "A"),
    ("Radio", "Cosa significa la sigla CQ?",
     {"A": "Chiamata urgente", "B": "Chiamata generale", "C": "Chiudo comunicazione"}, "B"),
    ("Radio", "Chi invento la radio?",
     {"A": "Tesla", "B": "Marconi", "C": "Hertz"}, "B"),
    ("Radio", "Cosa significa QTH?",
     {"A": "Frequenza", "B": "Posizione", "C": "Potenza"}, "B"),
    ("Radio", "Quale banda e usata da LoRa in Europa?",
     {"A": "433 MHz", "B": "868 MHz", "C": "915 MHz"}, "B"),
    ("Radio", "Cosa significa la sigla RST nei rapporti radio?",
     {"A": "Radio Signal Test", "B": "Readability Strength Tone", "C": "Receive Send Transmit"}, "B"),

    # Tecnologia
    ("Tech", "In che anno fu inviato il primo SMS?",
     {"A": "1985", "B": "1992", "C": "1999"}, "B"),
    ("Tech", "Cosa significa HTTP?",
     {"A": "HyperText Transfer Protocol", "B": "High Tech Transfer Program", "C": "Hyper Terminal Text Page"}, "A"),
    ("Tech", "Chi ha creato Linux?",
     {"A": "Bill Gates", "B": "Linus Torvalds", "C": "Steve Jobs"}, "B"),
    ("Tech", "Quanti bit ci sono in un byte?",
     {"A": "4", "B": "8", "C": "16"}, "B"),
    ("Tech", "Da dove prende il nome Python?",
     {"A": "Dal serpente", "B": "Dai Monty Python", "C": "Da un progetto NASA"}, "B"),
    ("Tech", "In che anno nasce il World Wide Web?",
     {"A": "1983", "B": "1989", "C": "1995"}, "B"),
    ("Tech", "Cosa significa IoT?",
     {"A": "Internet of Things", "B": "Input Output Terminal", "C": "Integrated Online Tech"}, "A"),
    ("Tech", "Quale azienda ha creato Arduino?",
     {"A": "Google", "B": "Una startup italiana", "C": "Microsoft"}, "B"),
    ("Tech", "Quanti Raspberry Pi sono stati venduti?",
     {"A": "10 milioni", "B": "60 milioni", "C": "100 milioni"}, "B"),
    ("Tech", "Cosa significa API?",
     {"A": "Advanced Program Interface", "B": "Application Programming Interface", "C": "Auto Protocol Integration"}, "B"),

    # Scienza
    ("Scienza", "A che velocita viaggia la luce?",
     {"A": "300.000 km/s", "B": "150.000 km/s", "C": "1.000.000 km/s"}, "A"),
    ("Scienza", "Quale pianeta e il piu vicino al Sole?",
     {"A": "Venere", "B": "Mercurio", "C": "Marte"}, "B"),
    ("Scienza", "Cos'e l'ISS?",
     {"A": "Un satellite GPS", "B": "La Stazione Spaziale", "C": "Un telescopio"}, "B"),
    ("Scienza", "Quale elemento chimico ha simbolo Fe?",
     {"A": "Fluoro", "B": "Ferro", "C": "Fosforo"}, "B"),
    ("Scienza", "Quanti pianeti ha il sistema solare?",
     {"A": "7", "B": "8", "C": "9"}, "B"),
    ("Scienza", "Cosa misura il barometro?",
     {"A": "Temperatura", "B": "Pressione atmosferica", "C": "Umidita"}, "B"),

    # Geografia
    ("Geo", "Qual e la montagna piu alta d'Italia?",
     {"A": "Monte Bianco", "B": "Monte Rosa", "C": "Gran Paradiso"}, "A"),
    ("Geo", "Quante regioni ha l'Italia?",
     {"A": "18", "B": "20", "C": "22"}, "B"),
    ("Geo", "Quale fiume attraversa Roma?",
     {"A": "Po", "B": "Tevere", "C": "Arno"}, "B"),
    ("Geo", "Qual e il lago piu grande d'Italia?",
     {"A": "Lago Maggiore", "B": "Lago di Como", "C": "Lago di Garda"}, "C"),
    ("Geo", "In quale mare sfocia il Po?",
     {"A": "Tirreno", "B": "Adriatico", "C": "Ligure"}, "B"),

    # Storia
    ("Storia", "In che anno cadde il muro di Berlino?",
     {"A": "1987", "B": "1989", "C": "1991"}, "B"),
    ("Storia", "Chi fu il primo uomo sulla Luna?",
     {"A": "Buzz Aldrin", "B": "Neil Armstrong", "C": "Yuri Gagarin"}, "B"),
    ("Storia", "In che anno nacque la Repubblica Italiana?",
     {"A": "1945", "B": "1946", "C": "1948"}, "B"),
    ("Storia", "Chi invento la pila elettrica?",
     {"A": "Volta", "B": "Galvani", "C": "Faraday"}, "A"),
    ("Storia", "In che anno fu fondata la NASA?",
     {"A": "1950", "B": "1958", "C": "1962"}, "B"),

    # Mesh & LoRa
    ("Mesh", "Quale modulazione usa LoRa?",
     {"A": "FSK", "B": "Chirp Spread Spectrum", "C": "QAM"}, "B"),
    ("Mesh", "Qual e il record di distanza LoRa?",
     {"A": "200 km", "B": "832 km", "C": "50 km"}, "B"),
    ("Mesh", "Cosa significa BBS?",
     {"A": "Broad Band Signal", "B": "Bulletin Board System", "C": "Basic Binary Service"}, "B"),
    ("Mesh", "In una rete mesh, cosa fa un repeater?",
     {"A": "Blocca i messaggi", "B": "Ripete i messaggi", "C": "Cripta i dati"}, "B"),
    ("Mesh", "Quale chip usa l'Heltec V3?",
     {"A": "SX1262", "B": "SX1276", "C": "CC1101"}, "A"),
    ("Mesh", "Cosa significa E2E encryption?",
     {"A": "Edge to Edge", "B": "End to End", "C": "Everywhere to Everywhere"}, "B"),
]


def _get_score(sender_key: str) -> Dict[str, int]:
    """Get or create score for user."""
    if sender_key not in _scores:
        _scores[sender_key] = {"score": 0, "correct": 0, "total": 0}
    return _scores[sender_key]


@CommandRegistry.register
class TriviaCommand(BaseCommand):
    """Trivia quiz game."""

    name = "trivia"
    description = "Quiz a risposta multipla"
    usage = "!trivia\n  !trivia A/B/C - rispondi\n  !trivia score - punteggio\n  !trivia top - classifica"
    aliases = ["quiz"]

    def __init__(self, session: Session):
        self.session = session

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        if not args:
            return self._new_question(ctx)

        arg = args[0].upper()

        if arg in ("SCORE", "PUNTI"):
            return self._show_score(ctx)
        elif arg in ("TOP", "CLASSIFICA"):
            return self._show_leaderboard()
        elif arg in ("A", "B", "C"):
            return self._answer(ctx, arg)
        else:
            return CommandResult.fail(
                "[BBS] Uso: !trivia | !trivia A/B/C | !trivia score | !trivia top"
            )

    def _new_question(self, ctx: CommandContext) -> CommandResult:
        """Send a new trivia question."""
        # Check if user already has an active question
        if ctx.sender_key in _active_questions:
            _, _, ts = _active_questions[ctx.sender_key]
            if time.time() - ts < QUESTION_TIMEOUT:
                # Resend the active question
                q_idx, correct, _ = _active_questions[ctx.sender_key]
                cat, question, options, _ = QUESTIONS[q_idx]
                opts = " ".join(f"{k}){v}" for k, v in options.items())
                return CommandResult.ok(
                    f"[BBS] [{cat}]\n{question}\n{opts}\nRispondi: !trivia A/B/C"
                )

        # Pick random question
        q_idx = random.randint(0, len(QUESTIONS) - 1)
        cat, question, options, correct = QUESTIONS[q_idx]

        # Store active question
        _active_questions[ctx.sender_key] = (q_idx, correct, time.time())

        opts = " ".join(f"{k}){v}" for k, v in options.items())
        return CommandResult.ok(
            f"[BBS] [{cat}]\n{question}\n{opts}\nRispondi: !trivia A/B/C"
        )

    def _answer(self, ctx: CommandContext, answer: str) -> CommandResult:
        """Check answer to active question."""
        if ctx.sender_key not in _active_questions:
            return CommandResult.fail(
                "[BBS] Nessuna domanda attiva. Usa !trivia"
            )

        q_idx, correct, ts = _active_questions[ctx.sender_key]

        # Check timeout
        if time.time() - ts > QUESTION_TIMEOUT:
            del _active_questions[ctx.sender_key]
            return CommandResult.fail(
                "[BBS] Tempo scaduto! Usa !trivia per una nuova domanda"
            )

        # Get question details
        cat, question, options, _ = QUESTIONS[q_idx]
        score = _get_score(ctx.sender_key)
        score["total"] += 1

        # Remove active question
        del _active_questions[ctx.sender_key]

        if answer == correct:
            points = 10
            score["score"] += points
            score["correct"] += 1
            pct = int(score["correct"] / score["total"] * 100)
            return CommandResult.ok(
                f"[BBS] Corretto! +{points}pt\n"
                f"Risposta: {options[correct]}\n"
                f"Punti: {score['score']} ({pct}% corrette)"
            )
        else:
            return CommandResult.ok(
                f"[BBS] Sbagliato!\n"
                f"Risposta: {correct}) {options[correct]}\n"
                f"Punti: {score['score']}"
            )

    def _show_score(self, ctx: CommandContext) -> CommandResult:
        """Show user's score."""
        score = _get_score(ctx.sender_key)

        if score["total"] == 0:
            return CommandResult.ok(
                "[BBS] Non hai ancora giocato. Usa !trivia"
            )

        pct = int(score["correct"] / score["total"] * 100)
        return CommandResult.ok(
            f"[BBS] {ctx.sender_display}:\n"
            f"  Punti: {score['score']}\n"
            f"  Risposte: {score['correct']}/{score['total']} ({pct}%)"
        )

    def _show_leaderboard(self) -> CommandResult:
        """Show top 5 scores."""
        if not _scores:
            return CommandResult.ok("[BBS] Nessun punteggio. Gioca con !trivia")

        # Sort by score descending
        top = sorted(_scores.items(), key=lambda x: x[1]["score"], reverse=True)[:5]

        lines = ["[BBS] Classifica Trivia:"]
        for i, (key, s) in enumerate(top, 1):
            # Try to get nickname
            try:
                from bbs.models.user import User
                from bbs.models.base import get_session
                with get_session() as session:
                    user = session.query(User).filter_by(public_key=key).first()
                    name = user.display_name if user else key[:8]
            except Exception:
                name = key[:8]

            lines.append(f"  {i}. {name} {s['score']}pt")

        return CommandResult.ok("\n".join(lines))
