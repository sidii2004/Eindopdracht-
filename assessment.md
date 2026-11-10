# Assessment DIP

## AlfaFlix eindopdracht

De applicatie bevat de verplichte login-, logging-, CRUD- en API-functionaliteit.
Daarnaast zijn reserveren, externe filminformatie via Wikipedia en een adminrol
toegevoegd. De API is gedocumenteerd in [swagger.yaml](./swagger.yaml) en het
stroomschema staat in [STROOMSCHEMA.md](./STROOMSCHEMA.md).

### Uitgevoerde functionaliteiten

- Registreren, inloggen, uitloggen en toegangsbeveiliging voor de videotheek.
- DVD's huren, terugbrengen en reserveren met statuscontrole.
- Logging van actie, gebruiker en timestamp.
- JSON API voor lezen, aanmaken, wijzigen, verwijderen, huren, reserveren en terugbrengen.
- Bootstrap template inheritance voor alle pagina's.
- Externe Wikipedia-API voor filmomschrijvingen en afbeeldingen.
- Adminpaneel voor DVD's beheren en logs bekijken.

De eerste geregistreerde gebruiker wordt administrator; alle volgende accounts
krijgen de gebruikersrol.

# Assignments

## Flask
- Aanmaken routes
- Aanmaken pagina's
- Formulier maken (bijvoorbeed contactformulier)
- 
- Telefoonboek (gekoppeld aan db)
- Film Portfolio (gekoppeld aan db)
- Documentatie site

### Fixes
- Fix security
- Fix missing imports
- Fix wrong routes
- Fix wrong templates

# Databases
- Database design
- ERD tekenen

# Telefoonboek
- Gekoppeld aan database
- Functionaliteiten:
    - Opzoeken telefoonnummer op basis van naam / nummer
    - Toevoegen telefoonnummer
    - Verwijderen telefoonnummer
    - Laten zien van alle telefoonummers
    - (Bonus) Bij meer dan 10 telefoonnummers een vorige/volgende pagina knop
    - (Bonus) Telefoonboek uitbreiden met adresgegevens, Xitter accounts etc.

# Film Portfolio
- Gekoppeld aan database
- Functionaliteiten
    - Laten zien wanneer welke films bekeken zijn
    - Films kunnen filteren op basis van genre, titel, acteurs etc.
    - 

# Documentatie site
- Laten zien van documentatie
- Laten zien welke documentatiepagina's er allemaal zijn (interactive)
- Toevoegen van nieuwe pagina
- Zoeken in documentatie
- 

# CSS met Bootstrap
- Zorg ervoor dat alle pagina's uniform en aantrekkelijk zijn vormgegeven.