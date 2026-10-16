# F04 — feit, citaat en afweging apart testen

Dated technical/research record; results and limitations apply to the versions described. Use [the README](../../README.md) for current status and planning.

16 oktober 2026. Door eigenaar goedgekeurde kleine vervolgproef na [het bronrelevantieonderzoek](citation-relevance.md). Alles blijft geïsoleerd in V2CHAT; geen app-, standaardmodel-, database-, CI- of afhankelijkheidswijziging.

## Kandidaat en vergelijking

`workflows/evidence_review.py` behoudt de keuze uit onopgeloste punten met een gekoppelde, door de workflow geschreven eigenaarstap. De AI levert apart:

- een relevante feitelijke premisse met één of twee exacte citaten, of geen premisse;
- een eventueel gebrek aan bewijs binnen de aangeleverde gegevens;
- de afweging waarom deze private controle redelijk is.

Ontbrekend bewijs hoeft dus niet met een willekeurig echt citaat te worden opgevuld. De code controleert structuur, bronlidmaatschap en bestaande beperkte claimregels. Zij bewijst geen betekenis, actualiteit of relevantie. Een gerichte test laat bewust zien dat een onjuiste premisse met een echt citaat nog door die vormcontrole kan komen. Alle modeluitvoer krijgt daarom een aparte inhoudelijke beoordeling; eigen modeltekst is geen verificatie.

Baseline is het vorige `BoundReview`-prototype met verplicht citaat en vrije reden. Het is geen volledige productievergadering. Beide armen gebruiken dezelfde canonieke CFO-persoonlijkheid, originele bronnen, targetcatalogus, geïnstalleerde Qwen2.5 14B en instellingen. Voor beide is de uitvoergrens vooraf op 600 tokens gezet om ruimte te bieden aan de extra velden; de vorige proef had 400. Vergelijk dus de armen binnen deze proef, geen scores tussen verschillende runs. Prompt en schema veranderen samen.

## Vooraf vastgelegd

Freeze: `audit-results/sprint7-reasoning/run-54d124a5e6c94b9e9c0d4ef1979f365b/freeze.json`. Elf bronbestanden, modelidentiteit, alle invoer en rubric vastgelegd vóór generatie. Script: `scripts/sprint7_evidence_review_experiment.py`.

Acht ontwikkelgevallen, één poging per arm, zestien modelaanroepen. De drie bekende contactvarianten plus vijf speciaal geschreven diagnoses: ontbrekend bewijs, verkeerde persoon, achterhaalde status, gedeeltelijke ondersteuning en meerdere relevante bronnen. Deze nieuwe gevallen zijn door de maker bekeken en zijn **ontwikkeldata**, geen ongeziene eindbeoordeling. De verwachte beoordelingen staan in de freeze maar gaan niet naar het model.

Per antwoord beoordeelt Codex als analist:

1. Wordt de feitelijke premisse ondersteund, gedeeltelijk ondersteund, tegengesproken of onvoldoende/irrelevant onderbouwd?
2. Is het bewijs ook relevant voor de gekozen controle, met juiste persoon en tijd? Een waar maar irrelevant feit is onvoldoende.
3. Wordt bewijsgebrek eerlijk beperkt tot de aangeleverde gegevens, zonder wereldwijde afwezigheid of geschiktheid te verzinnen?
4. Blijft de afweging bruikbaar en voorwaardelijk, met bekende feiten en bevoegdheidsgrenzen intact?

Normatieve afwegingen krijgen geen geforceerd feitelijk waar/onwaar-label. Een nuttige private controle mag bij ontbrekend bewijs. Alle ruwe fouten blijven bewaard; geen herstelpogingen, weggegooide antwoorden of automatische modelbeoordelaar. Bij synthetische gevallen zijn `meeting-01` t/m `meeting-05` uitsluitend opslagposities binnen bestaande retentie, geen vergaderingen met meerdere rollen.

Vooraf slagen 25 gerichte tests en Bandit medium/high. Geen nieuwe volledige integratieaudit. Onderzoeks- en modelbytes staan privé onder bestaande `sprint7-reasoning`-retentie; er is geen nieuwe opslagcategorie, modeldownload of externe verwerking.

## Resultaat

[Verificatie en volledige beoordelingen](../planning/f04-evidence-review-verification.json). Zestien van zestien antwoorden zijn vormgeldig, zonder herstelpogingen. Elf bronbestanden en modelidentiteit bleven gelijk. Alle antwoorden zijn als analist beoordeeld; eigenaaracceptatie is niet afgeleid.

**De kandidaat kiest in alle acht gevallen `premise: null`.** Hij levert daardoor nul feitelijke premisse/citaatparen. Dat mag bij bewijsgebrek en voorkomt decoratieve citaten, maar toont niet aan dat de nieuwe aanpak beschikbare feiten beter aan bewijs koppelt. Een percentage juiste citaten is bij nul citaten niet zinvol.

| Geval | Baseline | Kandidaat en beoordeling |
|---|---|---|
| A: contact deels onbekend | Irrelevant groepsgroottecitaat. | Geen decoratief citaat, maar spreekt al over de meest recent reagerende contactpersoon terwijl responsiviteit onbekend is. Dit vereist een voorwaardelijke formulering. |
| B: recent antwoord | Relevant citaat over onbekende eigen actuele zaak. | Eerlijk bewijsgebrek, maar benut het beschikbare relevante citaat niet. De private controle blijft bruikbaar. |
| C: geen antwoord/test | Andere route onderzoeken met zwak groepsgroottecitaat. | Geeft correct aan dat aangeleverde gegevens geen andere toegestane route tonen; verzint er geen en leidt geen desinteresse af. Afweging blijft algemeen. |
| Ontbrekend bewijs | Groepsgrootte als verplicht citaat is irrelevant. | Bewijsgebrek terecht benoemd, maar afweging verzint financiële gegevens/rolcriteria die niet bij de taak passen. |
| Verkeerde persoon | Gemengd citaat bewijst de geschiktheid van de bedoelde persoon niet; geen expliciete verkeerde persoonsattributie. | Correct geen geschiktheid van de andere persoon overnemen; voorwaardelijke private controle blijft mogelijk. |
| Achterhaalde status | Citeert terecht de huidige correctie. | Behoudt de huidige onzekerheid, maar verwijst naar CFO-criteria in plaats van concrete argumenten. Relevant citaat wordt niet gebruikt. |
| Gedeeltelijke ondersteuning | Bekende respons en onbekende geschiktheid blijven correct gescheiden. | Benoemt de onbekenden eerlijk. Geen samengestelde premisse gemaakt; succesvolle herkenning van gedeeltelijke ondersteuning is daarmee niet aangetoond. |
| Meerdere passende bronnen | Kiest een relevant citaat over onbekende geschiktheid. | Benoemt dat gebrek, maar valt terug op algemene financiële roltaal. Geen combinatie van ondersteunende citaten aangetoond. |

## Besluit en grens van deze proef

**Niet invoeren in de app.** Er is een gedeeltelijke verbetering bij eerlijk bewijsgebrek, maar geen aangetoonde verbetering in feit/citaatondersteuning en er zijn ongefundeerde of irrelevante afwegingen. F04 blijft open. De schemawijziging is geen betekeniscontrole; de nul-premisse-route kan niet als acht geslaagde bewijsredeneringen worden geteld.

Alle taken hebben een werkelijk onbekend te onderzoeken punt. Een lege premisse is daarom niet automatisch fout. Deze proef laat vooral zien dat de kandidaat de optie om geen citaat te geven gebruikt; de positieve route met relevante bekende feiten is niet aangetoond. Voor een volgende vergelijking moet die route expliciet in de rubric en gevallen worden afgedekt, zonder een willekeurig citaat verplicht te stellen.

Het volgende inhoudelijke voorstel is een beperkte contrastproef: hetzelfde onbekende punt, met respectievelijk een relevant bekend feit, een waar maar irrelevant feit en ontbrekend bewijs. Beoordeel behoud van relevante feiten, eerlijke onthouding en de afweging afzonderlijk. De criteria vooraf vastleggen; deze reeds bekeken gevallen blijven ontwikkeldata. Dat vervolg is nog niet gebouwd of gestart.

25 gerichte tests, Black en Bandit medium/high slagen. Geen nieuwe volledige integratieaudit, afhankelijkheid, standaardmodel-/appwijziging, push of merge. Alle modelaanroepen zijn afgerond; er draait geen verdere proef op de achtergrond.
