# F01 — bevestigde feiten als onbekend behandelen

Dated technical/research record; results and limitations apply to the versions described. Use [the README](../../README.md) for current status and planning.

15 oktober 2026. Eén afgebakende onderzoeksronde en een geïsoleerde lokale proef in V2CHAT. Drie primaire documentatiebronnen geselecteerd, geen repository gekloond, externe code gekopieerd of afhankelijkheid geïnstalleerd. Zoekvragen bevatten alleen algemene technische termen; de projectrecords en modelinvoer blijven lokaal.

## Bronnen en beslissing

| Bron | Aantoonbaar aanknopingspunt | Relevantie / beslissing | Risico en ontbrekende gegevens |
|---|---|---|---|
| [Ollama — Structured Outputs](https://docs.ollama.com/capabilities/structured-outputs) | “Provide a JSON schema to the `format` field.” | Bestaande native uitvoerbegrenzing behouden; geen nieuwe software. Idee/API-gebruik. | Geldige structuur bewijst geen juiste interpretatie. Licentie, laatste commit en beantwoording van issues: niet onderzocht/unknown. Extra afhankelijkheden voor deze proef: 0. |
| [Pydantic — Validators / Validation context](https://pydantic.dev/docs/validation/latest/concepts/validators/) | “You can pass a context object to the validation methods” | Bestaande validatie gebruiken om expliciete bronrelaties te controleren. Idee/API-gebruik. | Alleen controleerbare relaties afdwingbaar; geen algemene betekeniscontrole. Licentie, laatste commit en issue-respons: niet onderzocht/unknown. Extra afhankelijkheden voor deze proef: 0. |
| [Instructor — Validation and Reasking](https://python.useinstructor.com/concepts/reask_validation/) | “Good llm validation is just good validation” | Idee: brongebonden controle en concrete validatiefouten. Instructor zelf niet toevoegen. | Herhalen helpt alleen met een betrouwbare foutdetectie; een modelbeoordelaar kan dezelfde fout maken. Licentie, laatste commit, issue-respons en extra transitieve afhankelijkheden bij adoptie: unknown. Extra afhankelijkheden voor deze proef: 0. |

De bronnen tonen schema- en validatiemechanismen. Zij bewijzen **niet** dat ons feitprobleem daarmee is opgelost. Het voorstel hieronder is onze eigen ontwerpkeuze op basis van die mechanismen; geen overgenomen bewezen oplossing voor ons project. Geen externe codefragmenten gebruikt, dus geen broncode-hergebruikbesluit genomen.

## Kleine hypothese

De eerdere v4-proef plaatste correcties al achteraan en vroeg expliciet huidige feiten te respecteren. Dat voorkwam de fout niet. Deze proef maakt daarom een afzonderlijke actieve bronweergave: een expliciet beoordeeld achterhaald fragment wordt uitgesloten, terwijl de bijbehorende actuele correctie apart wordt benoemd. De originele bronnen en de vervangingsrelatie blijven in de privé-proefopslag staan.

`workflows/reviewed_evidence.py` accepteert exacte oude/actuele bronfragmenten plus het benoemde onderwerp/veld. Het leidt geen identiteit, toestemming, waarheid of vervangingsrelatie af uit vrije tekst. Dubbele velden, ontbrekende citaten, ambigue herhalingen, overlap en ketens worden geweigerd. Ongewijzigde tekst blijft behouden. Bij gedeeltelijke uitsluiting worden afzonderlijke bronfragmenten gemaakt; tekst vóór en na de uitsluiting wordt niet samengevoegd tot een nieuw citaat.

Dat een caller een vervanging opgeeft betekent nog niet dat de eigenaar die in de app heeft bevestigd. In deze proef zijn de twee relaties handmatig beoordeelde **ontwikkelfixture-metadata**. De app bevat nog geen algemene invoer/reviewstap voor zulke relaties. Daarom blijft dit buiten de productiestroom.

## Vooraf vastgelegde vergelijking

Script: `scripts/sprint7_fact_projection_experiment.py`.

- Dezelfde drie bekende ontwikkelvarianten: identiteit/status onbekend, recent antwoord, bevestigd niet getest/niet geantwoord.
- Alleen de CFO-eerste bijdrage, omdat die in v4 de concrete bekende-feitfout liet zien. Geen volledige vergadering of kritiekronde.
- Zelfde geïnstalleerde, eerder goedgekeurde Qwen2.5 14B, canonieke CFO-persoonlijkheid, schema en instellingen; één poging per arm, zes aanroepen totaal.
- Baseline: bestaande v4-eerste-voorstelbouwer, zonder de extra onafhankelijke-rondezin uit `run_rounds`, andere rolbijdragen of beoordelingen. Dit reproduceert niet de volledige eerdere foutgevende vergadering. Kandidaat: dezelfde basis met actieve bronprojectie plus expliciete actuele-feitmetadata. Dit zijn twee gekoppelde wijzigingen, geen bewijs welk onderdeel afzonderlijk helpt.
- Variant A heeft geen beoordeelde vervanging en houdt identieke baseline-/kandidaatinvoer. Het onbekende identiteitspunt wordt niet weggefilterd.
- Alle gegenereerde velden beoordelen: wordt een bekende antwoordstatus opnieuw onbekend? Wordt stilte verward met desinteresse? Kloppen reden, citaat en voorgestelde private vervolgstap?
- Vormvalidatie apart van inhoud beoordelen. Geen verborgen reparatie, tweede poging, weggelaten mislukking of herschreven antwoord.
- Proefinvoer en uitvoer staan onder de bestaande `sprint7-reasoning`-retentie, privé en genegeerd door Git. Geen nieuwe opslagcategorie.

Freeze: `audit-results/sprint7-reasoning/run-4eb5a374d1094823bc3bb4536c70a3dc/freeze.json`. Bronbestanden en modelidentiteit zijn vooraf vastgelegd.

## Uitkomst: kandidaat niet invoeren

[Verificatie en beoordeling](../planning/f01-projection-verification.json). Alle zes antwoorden zijn vormgeldig; geen herstelpogingen. De elf vastgelegde bronbestanden en geïnstalleerde modelidentiteit bleven gelijk. Alle zes antwoorden zijn inhoudelijk beoordeeld.

| Variant | Baseline | Kandidaat | Betekenis |
|---|---|---|---|
| A: identiteit/status deels onbekend | Privé de contactstatus onderzoeken; identiteit niet als bewezen voorstellen. | Identieke invoer en identiek voorstel. | De onbevestigde identiteit blijft onbekend. Geen verbetering; geen algemene bruikbaarheidspass. |
| B: contact reageerde | Eigen actuele zaak blijft terecht onbekend en wordt de voorgestelde controle. | Hetzelfde voorstel. | Geen teruggang, maar ook geen inhoudelijke winst. |
| C: contact testte niet en antwoordde niet | Een andere bestaande toegestane gesprekspartner onderzoeken. Citaat over historische groepsgrootte onderbouwt dat zwak. | Citeert de stilte correct, maar stelt alsnog voor de antwoordstatus van dezelfde persoon te onderzoeken. | Actueler citaat, slechtere vervolgstap. De geselecteerde onbekende gaat bovendien over een andere contactroute. F01 blijft open; ook inconsistentie zichtbaar. |

De baseline maakte de eerdere volledige-v4-feitfout in deze kleinere proef niet opnieuw. We kunnen dus geen herstelpercentage voor die eerdere fout rapporteren. Wel geeft de kandidaat op dezelfde stille-contactinvoer een minder bruikbare vervolgstap. Het vooraf gestelde verbetercriterium is niet gehaald. Geen invoering in de app, standaardmodelwijziging of merge.

Zestien gerichte tests slagen: expliciete bronvervanging, behoud van andere onbekenden/identiteiten, uitsluiting van verkeerde bronverwijzingen, botsingen/overlap/ketens, bestaande onafhankelijke-flowcontroles en bestaande proefretentie. Black-controle en Bandit medium/high slagen. Dit is geen nieuwe volledige integratieaudit.

## Voorstel voor verdere bespreking

Niet meteen nog meer promptregels of een nieuwe bibliotheek toevoegen. De concrete open vraag is nu: hoe koppelen we een voorgestelde controle aan een werkelijk onbekend veld, zodat vrije tekst niet alsnog een bevestigd feit opnieuw opent? Een volgend klein experiment kan expliciete actie-/onzekerheidsverwijzingen vergelijken met de huidige vrije aanbeveling. Dat bewijst op zichzelf nog geen goede afweging; de leesbare uitleg moet apart worden beoordeeld. Hiervoor is in deze ronde nog geen tweede kandidaat gebouwd of getest.

## Grenzen

Een model kan ook met actuele bronnen nog verkeerde vrije tekst produceren. Deze proef levert geen algemene tegenstrijdigheidsdetector en verandert geen appinstelling, bronrecord, database of standaardmodel. Ook een gunstige uitkomst rechtvaardigt nog geen volledige integratie: daarvoor zijn andere rollen, nieuwe gevallen en een bruikbaar eigenaarsoverzicht nodig. F02–F11 en de beveiligingsbevindingen blijven afzonderlijk open.
