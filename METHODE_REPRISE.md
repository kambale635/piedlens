# Methode de reprise du projet

Ce document guide toute nouvelle conversation ou reprise de session. Il complete `prompt_demarage.txt`, qui sert au demarrage initial du projet; il ne le remplace pas. Ne jamais deduire l'etat du code a partir d'un ancien resume seul : verifier les fichiers et les tests actuels.

## 1. Retrouver le bon etat

1. Confirmer le dossier racine du workspace et identifier les fichiers reellement presents. Ne pas supposer que Git, Docker, PostgreSQL ou des services locaux sont disponibles.
2. Lire integralement `.github/copilot-instructions.md`.
3. Lire integralement `evolution.md`. Reperer la derniere etape terminee, ses validations, les limites connues et le prochain travail autorise. Verifier ensuite cet etat dans le code et les tests.
4. Lire `docs/00-README.md` et les documents directement applicables au travail. Pour un Use Case, lire au minimum son contrat dans `docs/15-use-cases-catalog.md`, le document du bounded context, les invariants de `docs/16-business-invariants-and-rules.md`, puis les standards necessaires (`docs/17-documentation-standards.md`, `docs/22-error-handling-and-exceptions.md`, `docs/23-shared-kernel-value-objects.md`, `docs/14-event-driven-architecture.md`).
5. Lire l'implementation voisine, les ports, l'infrastructure, le wiring et les tests qui controlent le comportement. Identifier le vrai proprietaire de la decision avant toute modification.
6. Si une regle metier, une erreur, une transaction ou un contrat est ambigu ou contradictoire, ne pas inventer de valeur ni de comportement : exposer precisement la contradiction et demander une decision.

## 2. Une seule tache a la fois

- Respecter la regle 19 de `.github/copilot-instructions.md` : terminer une seule tache delimitee avant d'en commencer une autre.
- Suivre l'ordre explicitement valide par le proprietaire. Un feu vert pour une tache n'autorise pas automatiquement la suivante.
- Avant le code, confirmer le contrat, les invariants, les ports, les effets transactionnels et les cas d'erreur.
- Ecrire ou adapter un test de comportement cible, effectuer la plus petite modification coherente, puis lancer immediatement ce test.
- Ne pas presenter une hypothese comme une regle validee. Les seuils, politiques et valeurs variables viennent de la configuration documentee; pas de constantes metier improvisees.
- A la fin, mettre a jour `evolution.md` avec les fichiers touches, les validations reelles, les echecs ou limites et la prochaine etape. Presenter le bilan au proprietaire et attendre son feu vert.

## 3. Regles d'architecture et d'atomicite

- Respecter Clean Architecture, DDD, SOLID et les frontieres de bounded context. Le domaine ne depend pas de Django, ORM, Redis ou d'un autre contexte.
- Injecter les ports dans les Use Cases. Les adapters concrets et leur assemblage restent dans l'infrastructure et le composition root.
- Une operation modifie un seul Aggregate Root. Toute communication entre contextes passe par un contrat expose ou un evenement, jamais par un repository d'un autre contexte.
- Pour une ecriture qui emet un evenement, enregistrer l'agregat/la notification et l'evenement Outbox dans la meme transaction `transaction.atomic()` via le UnitOfWork du contexte (INV-TR-01/02). Ne jamais faire de dual-write base + Redis depuis le Use Case.
- Tout consumer evenementiel verifie et inscrit son marqueur `processed_events` dans la meme transaction que ses changements metier (INV-TR-03).
- Un adaptateur n'est transactionnel avec le UnitOfWork que si ses requetes utilisent la meme connexion/base active. Le demontrer par un test de commit et de rollback; ne pas conclure a l'atomicite sur la seule presence d'un context manager.

## 4. Commandes locales de validation

Pour les tests unitaires purs :

```bash
PYTHONPATH=src python3 -m unittest discover -s tests/unit/crm -p 'test_*.py' -v
```

Pour les tests Django d'integration, utiliser les settings de test du depot, pas les settings par defaut qui ciblent PostgreSQL :

```bash
python3 manage.py test tests.integration.crm --settings=config.test_settings -v 2
```

Pour verifier les migrations CRM :

```bash
python3 manage.py makemigrations crm --check --dry-run --settings=config.test_settings
```

Les tests locaux utilisent SQLite en memoire via `config.test_settings`; les settings standards requierent une configuration PostgreSQL. Une erreur d'authentification PostgreSQL ou de daemon Docker est un probleme d'environnement a diagnostiquer separement, pas la preuve d'un defaut applicatif. SQLite valide les commits/rollbacks dans ces tests mais ne prouve pas le comportement de concurrence PostgreSQL (`select_for_update`, `skip_locked`); conserver une validation PostgreSQL CI pour ces garanties.

Ne jamais afficher, copier dans le code ou commiter un secret. Utiliser les variables d'environnement et les fichiers d'exemple sans valeurs sensibles.

## 5. Point de reprise actuel

Etat verifie le 2026-09-28 :

- CRM : Outbox transactionnelle, historique d'achats CRM, alertes d'anomalie configurées et `MergeContactsUseCase` temps 1/2 sont présents. `INV-CRM-04` autorise exclusivement `OrderStatusChanged (paid_and_delivered)` et l'absorption du snapshot `ContactMerged`.
- Order Detection : les Use Cases du catalogue déjà couverts, dont le consommateur `ReassignContactReferencesFromContactMergedUseCase`, sont présents. Ce consumer modifie chaque Order/Candidate dans une transaction séparée et marque l'événement après les deux balayages.
- Dernière validation : tests unitaires CRM 28/28 et intégration CRM 17/17; tests unitaires Order Detection 39/39 et intégration Order Detection 12/12; aucune migration CRM ou Order Detection requise; system checks sans erreur.
- Le consumer CRM `ContactMerged` additionne le snapshot côté Contact principal avec un marqueur CRM atomique. Le consumer Order Detection consomme uniquement les IDs et ignore le snapshot CRM.
- Les achats CRM antérieurs à la migration d'historique ne sont pas reconstruits; aucun accès aux tables Order Detection n'est autorisé depuis CRM.
- **BLOQUANT AVANT MISE EN PRODUCTION** : le relay Outbox et la publication Redis Streams ne sont pas implémentés; les consumers ne sont donc pas branchés à un transport opérationnel. Les tests SQLite ne valident pas les garanties de concurrence PostgreSQL.
- Les écarts de persistance/contrat des segments et envois CRM signalés précédemment doivent encore être audités. Les schémas PostgreSQL natifs par bounded context restent également à configurer.

Apres chaque tache, actualiser cette section si l'etat de reprise change et consigner les resultats dans `evolution.md`.