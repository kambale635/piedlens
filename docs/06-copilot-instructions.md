# Instructions pour GitHub Copilot — à copier dans `.github/copilot-instructions.md`

> Copie le contenu ci-dessous (à partir de la ligne suivante) tel quel dans `.github/copilot-instructions.md` à la racine du repo. GitHub Copilot lit ce fichier automatiquement sur tous les comptes qui accèdent au repo — c'est ce qui garantit la cohérence entre tes différents comptes/sessions.

---

## Contexte du projet

Ce projet suit strictement **Clean Architecture**, **Domain-Driven Design (DDD)**, et les **principes SOLID**. Toute suggestion de code DOIT respecter les règles ci-dessous. La documentation complète et faisant foi est dans `/docs` — consulte-la avant de générer du code sur un contexte que tu ne connais pas encore.

## Règles non négociables

1. **Règle de dépendance** : le code dans `/domain` ne doit jamais importer de librairie technique (pas de client Redis, pas d'ORM, pas de SDK d'API externe). Le domaine ne dépend que de lui-même et d'interfaces qu'il définit.

2. **Injection de dépendances uniquement** : jamais de `new ConcreteClass()` d'une classe d'infrastructure à l'intérieur d'un Use Case ou d'une classe de domaine. Toute dépendance externe est reçue par constructeur, typée par interface.

3. **Un agrégat = une transaction** : ne jamais modifier deux Aggregate Roots dans la même transaction/méthode. Si une opération semble nécessiter de modifier `Order` et `Contact` en même temps, c'est un signal qu'il faut passer par un événement de domaine (`OrderStatusChanged` publié, consommé séparément par le contexte CRM).

4. **Value Objects immuables** : toute donnée avec une règle de validation (montant, devise, numéro de téléphone, email) doit être encapsulée dans un Value Object avec validation à la construction — jamais un simple `string`/`number` nu qui circule dans le code métier.

5. **Pas de logique métier dans les contrôleurs/webhooks** : un contrôleur REST ou un handler de webhook ne fait que (a) valider/parser la requête entrante, (b) appeler un Use Case, (c) formatter la réponse. Zéro `if` de logique métier à cet endroit.

6. **Respect des frontières de bounded context** : le code du contexte `order-detection` ne doit jamais importer directement une classe du contexte `crm` (ou inversement) — la communication passe par événements de domaine ou par une interface explicitement exposée en `application`.

7. **Tests obligatoires pour le domaine** : toute nouvelle règle métier dans `/domain` doit être accompagnée d'un test unitaire sans I/O. Ne jamais suggérer du code de domaine sans son test associé.

8. **Sécurité par défaut** : ne jamais suggérer de stocker un secret, un token, ou une clé API en clair dans le code ou dans un fichier commité. Toujours passer par variables d'environnement.

9. **Multilingue/multi-devise natif** : ne jamais coder en dur une chaîne de langue (ex: `if (message.includes("payé"))`), une devise, ou un format de nombre dans le domaine ou l'application. Toute donnée de ce type vient du `Rules Engine` (voir `/docs/08-context-rules-engine.md`).

10. **Avant de générer un nouveau module** : vérifie d'abord si un fichier `/docs/0X-context-*.md` correspondant existe. S'il n'existe pas pour ce que tu t'apprêtes à coder, arrête-toi et demande une clarification plutôt que d'improviser l'architecture.

11. **Jamais de publication d'événement hors transaction** : toute émission d'événement de domaine passe par la table `outbox_events` du contexte, dans la même transaction PostgreSQL que la sauvegarde de l'agrégat — jamais un appel direct à Redis depuis un Use Case. Voir `/docs/14-event-driven-architecture.md`.

12. **Idempotence obligatoire côté consommateur** : tout consommateur d'événement vérifie la table `processed_events` avant traitement, sans exception.

13. **Stack technique imposée** : Python/Django, monolithe modulaire (une app Django par bounded context), PostgreSQL unique avec schémas séparés par contexte. Ne jamais suggérer d'introduire un autre langage ou une base de données séparée sans que ce soit explicitement demandé — voir `/docs/13-technology-decision-adr.md` pour la justification complète.

14. **Documentation obligatoire style senior/framework** : toute classe publique, tout Use Case, toute méthode qui protège un invariant métier référencé dans `/docs/16-business-invariants-and-rules.md` doit avoir un docstring complet suivant les gabarits de `/docs/17-documentation-standards.md`, citant l'identifiant de règle (`INV-XX-NN`) concerné. Un code sans cette documentation est considéré incomplet, jamais acceptable "à documenter plus tard".

15. **Avant d'implémenter un Use Case, vérifier son contrat exact** dans `/docs/15-use-cases-catalog.md` (entrée, sortie, préconditions, erreurs, événements publiés) — ne jamais inventer une signature différente de celle documentée. Si le Use Case demandé n'y figure pas, l'ajouter au catalogue d'abord, puis l'implémenter.

16. **Aucune vérification d'accès en dur** : toute vérification d'authentification, de tenant (merchant), ou de permission passe exclusivement par la chaîne de middleware (`/docs/21-middleware-layer.md`) et `IPermissionChecker` (`/docs/20-context-access-control.md`). Zéro `if user.role == "..."` où que ce soit dans le code applicatif ou domaine.

17. **Gestion des exceptions uniforme** : toute exception levée suit la hiérarchie et le mapping de `/docs/22-error-handling-and-exceptions.md`. Aucun contrôleur ne formate lui-même une réponse d'erreur — l'`ExceptionHandlingMiddleware` est le seul point de traduction. Aucune stack trace ou détail technique ne fuit jamais dans une réponse HTTP.

18. **Value Objects communs** : avant de créer un nouveau Value Object (Money, téléphone, email, identifiant...), vérifier `/docs/23-shared-kernel-value-objects.md` — ne jamais dupliquer un concept déjà défini dans le shared kernel avec une validation différente.

19. **Discipline d'exécution — une tâche à la fois, rien oublié** : traite toujours un seul Use Case (ou une seule tâche clairement délimitée) à la fois, jusqu'à complétion totale — code, docstring conforme à `/docs/17-documentation-standards.md`, gestion d'erreurs conforme à `/docs/22-error-handling-and-exceptions.md`, et au moins un test. Ne demande pas d'approbation intermédiaire et ne t'arrête pas après un plan ou une étape partielle : poursuis la checklist et la feuille de route jusqu'à ce que chaque élément soit terminé. Arrête-toi uniquement si une contradiction documentaire empêche de définir le contrat; pose alors une seule question groupée. Si une tâche touche plusieurs contextes, termine-la contexte par contexte, jamais en superficiel sur tous à la fois. Mets à jour `evolution.md` au début avec une ligne par Use Case et son statut, puis maintiens les statuts à jour.

## Style de code attendu

- Noms explicites, en anglais pour le code (variables, classes, fonctions), en français toléré uniquement dans les commentaires si l'équipe le préfère — mais rester cohérent sur tout le repo.
- Fonctions courtes, une responsabilité par fonction (cohérent avec SRP).
- Préférer la composition à l'héritage, sauf cas DDD explicite (Entity/Aggregate Root).
- Toute Pull Request générée avec l'aide de Copilot doit être relue avec la checklist de `/docs/03-solid-principles.md` avant merge.

## Quand Copilot n'est pas sûr

Si une demande de code ne précise pas dans quel bounded context ou quelle couche elle doit vivre, Copilot doit **poser la question** plutôt que de deviner et créer un fichier au mauvais endroit — un mauvais placement initial coûte plus cher à corriger qu'une question posée à temps.
