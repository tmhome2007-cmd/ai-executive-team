# F01 — een eigenaarstap aan een onbekend punt koppelen

Dated technical/research record; results and limitations apply to the versions described. Use [the README](../../README.md) for current status and planning.

15 oktober 2026. Door de eigenaar gevraagde vervolgproef in V2CHAT. De eerdere [bronprojectieproef](known-facts.md) blijft afgewezen. Deze nieuwe kandidaat gebruikt opnieuw de originele bronnen, inclusief historische informatie, en verandert de koppeling tussen onzekerheid en voorgestelde controle. Geen nieuwe afhankelijkheden, internetonderzoek, downloads of externe verwerking.

## Wat is gebouwd

`workflows/bound_review.py` laat het model een `target_id` kiezen uit expliciet aangeleverde onopgeloste punten. Bij elk ID hoort één workflowvraag en één vooraf geschreven private eigenaarstap. De native uitvoerschema-enum en de runtimevalidatie sluiten andere IDs uit. De weergave controleert de keuze opnieuw en haalt de bijbehorende vraag/stap uit dezelfde catalogus. Het model kan geen vrije actievelden toevoegen. Een bekende antwoordstatus kan daardoor niet als aparte stap verschijnen als het ID terecht ontbreekt.

De catalogus en lijst onopgeloste punten zijn **applicatie-invoer**, geen onafhankelijk ontdekte modelkennis. De proef gebruikt bestaande intake-regels om die lijst te bepalen. Het model kiest het punt en schrijft reden, citaat en eventuele aanname. De getoonde stap is uitdrukkelijk applicatiebegeleiding, geen modelgeschreven voorstel. Er wordt niets uitgevoerd of geautoriseerd.

De keuze kan inhoudelijk nog verkeerd zijn, en vrije uitleg kan nog een bekend feit heropenen. Een gerichte test demonstreert dat deze semantische fout door de vormcontrole heen kan komen. Daarom tellen geldig JSON, een geldig ID en de vooraf geschreven eigenaarstap niet als een geslaagde redenering. Lege, dubbele of onbekende onopgeloste IDs worden geweigerd; de proef verzint dan geen ontbrekende informatie.

## Vooraf vastgelegde vergelijking

Script: `scripts/sprint7_bound_review_experiment.py`.

- Drie bekende ontwikkelvarianten: identiteit/contactstatus deels onbekend (A), recent antwoord (B), bevestigd niet getest en niet geantwoord (C).
- Baseline: dezelfde vrije CFO-eerste-voorstelbouwer als in de vorige kleine proef. Kandidaat: gekozen onzekerheids-ID met de bijbehorende workflowstap. Geen volledige vergadering of beoordeling door andere rollen.
- Dezelfde originele bronbytes, vraag, canonieke CFO-persoonlijkheid, geïnstalleerde Qwen2.5 14B en inference-instellingen. Nieuwe prompt en nieuw schema zijn gekoppelde wijzigingen; geen afzonderlijke causale claim.
- Eén poging per arm, zes aanroepen totaal. Alle ruwe antwoorden behouden, ook bij validatiefalen. Geen reparatie of selectie van een gunstige herhaling.
- Beoordeel de geselecteerde controle én alle vrije uitleg/aannamevelden: behoud van bekende feiten, relevante onzekerheid, passende onderbouwing, geen verzonnen identiteit/interesse/toestemming, geen herhaling van het bekende budget.
- De modelkeuze moet bruikbaar zijn; een geldig ID alleen is onvoldoende. Een stap die de workflow levert wordt niet als zelfstandig modelplannen gescoord.

Freeze: `audit-results/sprint7-reasoning/run-88e04a7489ae4a45b5465437509440c9/freeze.json`. Negen bronbestanden, modelidentiteit, catalogus, invoer en rubric zijn vóór generatie vastgelegd. Proefbytes vallen onder bestaande genegeerde `sprint7-reasoning`-opslag en dertigdaagse retentie.

Vooraf: 21 gerichte tests slagen, Black en Bandit medium/high slagen. Bandit zag aanvankelijk ten onrechte SQL in de promptzin over het kiezen van een ID; die zin is herformuleerd zonder onderdrukking van de controle. Geen volledige nieuwe integratieaudit.

## Uitkomst

[Verificatie en beoordelingen](../planning/f01-bound-review-verification.json). Alle zes antwoorden zijn vormgeldig, zonder herstelpogingen; alle negen bronbestanden en modelidentiteit bleven gelijk. Alle zes antwoorden zijn inhoudelijk beoordeeld.

| Variant | Baseline | Kandidaat | Beoordeling |
|---|---|---|---|
| A: identiteit/status deels onbekend | Contactstatus onderzoeken, met correctie over de onbekende identiteit als bron. | Kiest contactstatus; de gekoppelde stap houdt verschillende personen apart. Citeert echter historische groepsgrootte. | Geen verzonnen identiteit of heropening van bevestigd feit. Onderbouwing verslechtert ten opzichte van baseline. |
| B: contact reageerde | Eigen actuele zaak onderzoeken; relevant citaat. | Kiest precies die onbekende en krijgt een private controle van bestaande gegevens; relevant citaat. | Koppeling klopt, maar geen aangetoonde inhoudelijke winst. De concretere stap komt uit de catalogus. |
| C: contact reageerde niet | Andere toegestane gesprekspartner onderzoeken; zwak groepsgroottecitaat. | Kiest de andere contactroute, zonder bekende antwoordstatus opnieuw te controleren; eveneens zwak groepsgroottecitaat. | De koppeling werkt en de vrije uitleg heropent het bekende feit hier niet. Uitleg over effectiviteit blijft generiek tegenover het gewenste echte-gebruikersfeedbackdoel. |

**Smalle uitkomst:** de drie kandidaatacties zijn correct aan de aangeleverde onbekende punten gekoppeld; hun vrije uitleg bevat in deze proef geen heropening van de bekende antwoordstatus. Die eigenschap van de stappen wordt afgedwongen door het schema en de workflowcatalogus, niet bewezen als zelfstandige modelredenering. De baseline behoudt deze bekende feiten in deze proef ook. Er is dus geen gemeten herstel van een opnieuw gereproduceerde baselinefout en geen bewezen algemene kwaliteitswinst.

**Besluit:** prototype bewaren, niet aansluiten op de app. De inhoudelijke verbeterpoort is niet gehaald: bronrelevantie blijft zwak en gaat in A achteruit. F01 blijft als bredere feiten-/interpretatiekwestie open. Geen standaardmodelwijziging, extra afhankelijkheid, push of merge. De vorige mislukte bronprojectieproef is ongewijzigd bewaard.

De 21 gerichte tests en controles hierboven gelden voor deze geïsoleerde wijziging. Geen nieuwe volledige integratieaudit of eigenaaracceptatie. Geen modelproef blijft op de achtergrond draaien.

## Volgende bespreekpunt

De stap en de onbekende zijn nu controleerbaar gekoppeld. De volgende inhoudelijke zwakte is waarom het geselecteerde bewijs de keuze ondersteunt (F04). Een groepsgrootte zegt niets over actuele bereidheid of geschiktheid. Een volgende proef zou de reden aan concreet relevant bewijs moeten verbinden en ook eerlijk ontbreken van bewijs toestaan. Dat vervolg is hier nog niet uitgevoerd.
