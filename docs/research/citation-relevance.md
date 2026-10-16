# F04 — onderzoek naar bewijs dat het advies ondersteunt

Dated technical/research record; results and limitations apply to the versions described. Use [the README](../../README.md) for current status and planning.

Vervolg, 16 oktober: de eigenaar heeft de voorgestelde proef goedgekeurd. [Uitvoering en resultaat](evidence-review.md):16vormgeldige antwoorden, maar de kandidaat maakt geen feit/citaatparen en voegt soms ongeschikte afwegingen toe. Geen appadoptie; onderstaande onderzoeksbevindingen blijven de eerdere uitgangspunten.

15 oktober 2026. Alleen onderzoek en een voorstel voor de volgende proef. V2CHAT, branch `codex/sprint-7-actionable-schema`, HEAD `58b9992` met de bestaande onvoltooide lokale wijzigingen. Geen code gewijzigd, model aangeroepen, afhankelijkheid toegevoegd, externe code uitgevoerd of private projecttekst naar een zoekdienst gestuurd. Drie externe projecten onderzocht via vijf primaire pagina's; geen brede crawl.

## Wat in onze eigen code misgaat

De vorige [gekoppelde-stappenproef](bound-review.md) is opnieuw gecontroleerd, inclusief ruwe kandidaatantwoorden en de schema's die werkelijk aan het model zijn gegeven. De hashes komen overeen met de bewaarde verificatie.

| Variant | Mogelijke exacte citaten in werkelijk schema | Keuze en betekenis |
|---|---:|---|
| A: identiteit/contactstatus deels onbekend | 37 | Kiest historische groepsgrootte voor onderzoek naar huidige responsiviteit. De correctie over onbekende identiteit was ook beschikbaar. |
| B: recent antwoord | 36 | Kiest de expliciete onbekendheid van een eigen actuele zaak. Dat ondersteunt het te onderzoeken punt. |
| C: bevestigd geen antwoord/test | 36 | Kiest groepsgrootte voor onderzoek naar een andere toegestane tester. De correctie over niet-antwoorden en ontbreken van een bevestigde tester was ook beschikbaar. |

De ontbrekende relevante tekst is dus niet de verklaring voor deze twee keuzes. `quotation_choices` maakt een algemene lijst van bronfragmenten, regels en zinnen. De native schema's koppelen bron-ID aan een echt citaat, maar niet dat citaat aan de specifieke reden. `verify_evidence_quotes` controleert alleen bron-ID en tekstlidmaatschap. `BoundReview` vereist altijd een `fact`, ook als passend bewijs ontbreekt. Een algemene reden en een willekeurig echt citaat kunnen daardoor tegelijk slagen.

Dit bewijst een gat in de controle, niet waarom het model juist dit citaat prefereert. Contextvolgorde, korte tekst, rolpersoonlijkheid en modelbeperkingen zijn mogelijke verklaringen, niet geïsoleerd aangetoonde oorzaken. Meer bronfragmenten of grotere context zijn nog geen bewezen oplossing.

## Wat de externe bronnen toevoegen

| Project / primaire bron | Kort aanknopingspunt uit de bron | Bruikbaar idee en belangrijkste grens |
|---|---|---|
| [ALCE-paper, §3.3 en beperkingen](https://aclanthology.org/2023.emnlp-main.398.pdf) | “citation precision, which identifies any irrelevant citations” | Onderzoek of een concrete bewering door haar citaten wordt gedragen, naast antwoordkwaliteit. De paper noemt ook beperkingen van automatische inferentie en gedeeltelijke ondersteuning. Het is onderzoek naar antwoorden met citaten, geen bewijs voor optimale bedrijfskeuzes. |
| [ALCE-evaluatiecode](https://github.com/princeton-nlp/ALCE/blob/main/eval.py) | “Run inference for assessing AIS between a premise and hypothesis.” | `_run_nli_autoais` vergelijkt passage en bewering; `compute_autoais` verwerkt citaten. Dit is geen eenvoudige tekstmatch. De code laadt een afzonderlijk model via `from_pretrained`; niet overnemen of uitvoeren in deze ronde. |
| [Ragas — Faithfulness](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/) | “A response is considered faithful if all its claims can be supported by the retrieved context.” | Splits het antwoord op in feitelijke beweringen en beoordeel hun ondersteuning. Een modelbeoordeling blijft een beoordeling, geen onafhankelijke waarheid. Het getoonde voorbeeld gebruikt een cloudmodel; dat voorbeeld voeren we niet uit. |
| [Ragas — Response Relevancy](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/answer_relevance/) | “without evaluating factual accuracy” | Antwoordrelevantie en feitelijke ondersteuning apart meten. Hun vraag-/embeddingvergelijking is geen bewijs dat ons specifieke citaat de redenering ondersteunt. |
| [LlamaIndex — CitationQueryEngine](https://developers.llamaindex.ai/python/examples/query_engine/citation_query_engine/) | “here we can control how granular citation sources are” | Kleine inspecteerbare bronfragmenten met toegang tot de werkelijke bron. Het voorbeeld toont bronverwijzing, geen garantie op juiste ondersteuning; installeren zou ons huidige gat niet aantoonbaar sluiten. |

Voor **ALCE, Ragas en LlamaIndex afzonderlijk** geldt: oordeel **idee alleen**. Code-/modellicentie, laatste commitdatum, responstijd op issues en aantal extra transitieve afhankelijkheden bij adoptie zijn **unknown** binnen deze begrensde ronde. Geen licentie of onderhoudsstatus gegokt. Er is geen externe code gekopieerd; eventuele latere adoptie vraagt eerst controle van de precieze versie en licentie. Werkelijk toegevoegde afhankelijkheden nu: **0**.

## Het onderscheid dat de oplossing nodig heeft

Onze conclusie uit de bronnen en lokale fouten: vier afzonderlijke vragen beantwoorden.

1. **Herkomst:** bestaat dit citaat echt in deze bron? Dat controleren we al.
2. **Ondersteuning:** draagt het citaat deze specifieke feitelijke bewering? Groepsgrootte bewijst geen huidige bereidheid of geschiktheid.
3. **Actualiteit en onderwerp:** gaat het over de juiste persoon, tijd en bevestigde correctie? Een echt historisch citaat kan nu achterhaald zijn.
4. **Afweging:** maakt dit feit de voorgestelde controle redelijk onder de gegeven beperkingen? Dit is een redenering, geen feit dat een citaat automatisch bewijst.

Bijvoorbeeld: bevestigd niet-antwoorden ondersteunt de bewering dat er na eerder contact geen antwoord kwam. Een andere bestaande contactroute onderzoeken kan daarop een redelijke voorwaardelijke vervolgstap zijn. Het bewijst niet dat de eerdere persoon geen interesse heeft, dat een andere tester bestaat of dat dit de gegarandeerd beste strategie is. Deze duiding is onze toepassing op het project, geen resultaat dat de externe bronnen voor ons systeem hebben vastgesteld.

## Mogelijke oplossingen vergeleken

| Aanpak | Mogelijk voordeel | Beperking / oordeel |
|---|---|---|
| Alleen meer nadruk op relevante citaten in de prompt | Kleine wijziging. | De instructie om beslissend bewijs te kiezen bestaat al; geen nieuwe voldoende oplossing. |
| Fragmenten rangschikken op woord-/embeddingovereenkomst | Kan irrelevante context verminderen. | Woordoverlap bewijst geen ondersteuning; gevaar voor selectie van hetzelfde onderwerp met verkeerde persoon/tijd. Nu geen retriever of embeddingmodel toevoegen. |
| Feitelijke bewering expliciet aan citaat koppelen; afweging en bewijsgebrek apart | Maakt zichtbaar wat precies bewezen zou moeten zijn en voorkomt een verplicht decoratief citaat. | De relatie kan nog onjuist worden ingevuld. Eerst een kleine vergelijking met onafhankelijke handmatige beoordeling, geen automatische betekenisgarantie. **Voorkeur voor de volgende proef.** |
| Een tweede model of NLI-model laten oordelen | Kan verdachte bewering/citaatparen markeren. | Beoordelaar kan zich vergissen; extra aanroepen, eventuele nieuwe modelgewichten en onderhoud. Pas zinvol na ijking tegen vastgelegde menselijke/analistlabels; nu niet installeren. |

## Voorstel voor een volgende proef — nog niet gebouwd

Behoud de koppeling tussen onbekend punt en eigenaarstap. Laat het model daarnaast de feitelijke premisse benoemen met bijbehorend citaat, en de afweging apart formuleren. Sta expliciet toe: **onvoldoende relevant bewijs in de aangeleverde gegevens**. Dat betekent niet dat er buiten die gegevens geen bewijs of contact bestaat. Een eigen label van het model geldt niet als verificatie.

Leg vóór generatie een rubric vast voor: ondersteund, gedeeltelijk ondersteund, tegengesproken en onvoldoende/irrelevant bewijs. Beoordeel de feitelijke premisse afzonderlijk van de bruikbaarheid van het advies. Normatieve afwegingen krijgen geen geforceerd waar/onwaar-citaatlabel. Geen hoog totaalcijfer door alleen onschadelijke geciteerde feiten te herhalen.

Gebruik eerst bekende ontwikkelvoorbeelden met een relevant citaat, een waar maar irrelevant citaat, ontbrekend bewijs, verkeerde persoon, verouderde status en een gedeeltelijk ondersteunde samengestelde bewering. Houd ook een geval met meerdere passende bronnen; dwing geen enkele voorkeursformulering af. Beoordeel of het model een gebrek aan bewijs eerlijk meldt zonder nuttige voorwaardelijke vervolgstappen te laten vallen. Nieuwe eindbeoordelingsgevallen vooraf apart vastleggen; alles wat in onderzoek of ontwikkeling is bekeken niet achteraf ongezien noemen.

Pas als bewering/citaatparen inhoudelijk beter worden zonder verlies van feitenbehoud of bruikbaarheid, volgt een proef met andere rollen en de normale flow. Nog geen codewijziging, nieuw modelresultaat, appadoptie, push, merge of sprintafronding uit dit onderzoek afleiden.
