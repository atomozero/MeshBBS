"""
Fortune command for MeshCore BBS.

Random quotes, proverbs, and fun facts.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import random
from typing import List

from sqlalchemy.orm import Session

from .base import BaseCommand, CommandContext, CommandResult, CommandRegistry

FORTUNES = [
    # Proverbi italiani
    "Chi dorme non piglia pesci.",
    "L'unione fa la forza.",
    "Chi la dura la vince.",
    "Meglio tardi che mai.",
    "Non tutto il male vien per nuocere.",
    "Chi troppo vuole nulla stringe.",
    "A caval donato non si guarda in bocca.",
    "Chi fa da se fa per tre.",
    "Il mattino ha l'oro in bocca.",
    "Chi semina vento raccoglie tempesta.",
    "Tra il dire e il fare c'e di mezzo il mare.",
    "L'appetito vien mangiando.",
    "Chi trova un amico trova un tesoro.",
    "Sbagliando si impara.",
    "La fretta e cattiva consigliera.",
    "Ogni lasciata e persa.",
    "Chi va piano va sano e va lontano.",

    # Curiosita radio/mesh
    "La prima trasmissione radio fu di Marconi nel 1895.",
    "LoRa puo raggiungere oltre 700km in condizioni ideali.",
    "Il segnale radio viaggia a 300.000 km/s.",
    "La ISS trasmette in APRS a 145.825 MHz.",
    "Il primo BBS fu creato nel 1978 a Chicago.",
    "La rete mesh non ha un singolo punto di guasto.",
    "LoRa usa la modulazione chirp spread spectrum.",
    "Il record di distanza LoRa e 832 km (2020).",

    # Curiosita tecnologia
    "Il primo SMS fu inviato nel 1992: 'Merry Christmas'.",
    "Il primo sito web e ancora online: info.cern.ch",
    "Linux nasce nel 1991 come progetto universitario.",
    "Il Raspberry Pi ha venduto oltre 60 milioni di unita.",
    "Python prende il nome dai Monty Python, non dal serpente.",
    "Il primo computer bug era un vero insetto (1947).",
    "Il WiFi non e un acronimo di nulla.",
    "Il codice Morse SOS non sta per 'Save Our Souls'.",
    "Arduino prende il nome da un bar di Ivrea.",
    "Il GPS richiede almeno 4 satelliti per il fix 3D.",

    # Motivazionali
    "La radio unisce le persone oltre ogni confine.",
    "Ogni nodo della rete mesh rende tutti piu forti.",
    "La conoscenza condivisa e conoscenza moltiplicata.",
    "Nel mesh, nessuno e solo.",
    "73 e il codice per 'migliori saluti' in CW.",
]


@CommandRegistry.register
class FortuneCommand(BaseCommand):
    """Display a random quote or fun fact."""

    name = "fortune"
    description = "Messaggio del giorno casuale"
    usage = "!fortune"
    aliases = ["quote", "citazione"]

    def __init__(self, session: Session):
        self.session = session

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        quote = random.choice(FORTUNES)
        return CommandResult.ok(f"[BBS] {quote}")
