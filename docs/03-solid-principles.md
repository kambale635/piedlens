# Application des principes SOLID sur ce projet

Ce fichier existe pour que Copilot (et toi, en relecture) puisse vérifier concrètement chaque suggestion de code contre ces 5 règles. Chaque principe est illustré avec un exemple **de ce projet précis**, pas un exemple générique.

---

## S — Single Responsibility Principle

**Règle** : une classe a une seule raison de changer.

**Application concrète** : `OrderDetectionUseCase` (couche Application) orchestre, mais ne contient **aucune** logique de détection elle-même — elle délègue à `OrderDetectionService` (domaine). Si demain la logique de détection change, on ne touche qu'au Domain Service. Si demain le format de la requête API change, on ne touche qu'au Use Case ou au contrôleur.

❌ **À rejeter si Copilot propose** : une classe `OrderController` qui contient à la fois la validation HTTP, la logique de détection de paiement, ET la requête SQL. C'est 3 responsabilités, donc 3 raisons de changer, donc une violation.

---

## O — Open/Closed Principle

**Règle** : ouvert à l'extension, fermé à la modification.

**Application concrète** : `IRuleEvaluator` (voir `02-domain-model.md`) est une interface stable. Ajouter un nouveau type de détection (ex : reconnaissance d'image de reçu par OCR) = créer une nouvelle classe `OcrPaymentProofEvaluator implements IRuleEvaluator`, l'enregistrer dans le conteneur d'injection de dépendances. **Zéro ligne modifiée** dans `OrderDetectionService` ou ailleurs.

C'est ce principe qui permet ton exigence "s'adapter à tout pays/plateforme sans réécrire le code" : chaque nouvelle langue = nouvelle donnée de configuration, chaque nouvelle plateforme = nouvelle classe qui implémente un port existant.

---

## L — Liskov Substitution Principle

**Règle** : une sous-classe/implémentation doit pouvoir remplacer son interface sans casser le comportement attendu.

**Application concrète** : `WhatsAppConnector` et `InstagramConnector` implémentent tous deux `IPlatformConnector`. N'importe quel Use Case qui dépend de `IPlatformConnector` doit fonctionner **identiquement** peu importe laquelle des deux implémentations est injectée — aucune vérification de type (`if (connector instanceof WhatsAppConnector)`) n'est tolérée dans la couche Application. Si une plateforme a un comportement fondamentally différent (ex : pas de support des messages vocaux), l'interface doit être repensée (méthode optionnelle explicite ou interface séparée — voir ISP ci-dessous), pas contournée par un `if`.

---

## I — Interface Segregation Principle

**Règle** : préférer plusieurs interfaces petites et spécifiques à une seule interface généraliste.

**Application concrète** : au lieu d'un `IPlatformConnector` monolithique avec 15 méthodes (dont certaines non supportées par certaines plateformes), on sépare :
```
IMessageFetcher       (fetchNewMessages)
IMessageSender        (sendMessage) 
IMediaDownloader      (downloadMedia)
IAccountHealthChecker (checkAccountStatus)
```
Un connecteur n'implémente que les interfaces pertinentes pour ses capacités réelles. Ça évite les méthodes `throw new NotSupportedException()` qui sont un symptôme classique de violation ISP.

---

## D — Dependency Inversion Principle

**Règle** : les modules de haut niveau ne dépendent pas des modules de bas niveau ; les deux dépendent d'abstractions.

**Application concrète** : `OrderDetectionUseCase` (haut niveau, Application) dépend de l'interface `IOrderRepository` (définie dans le Domain), jamais de `PostgresOrderRepository` (bas niveau, Infrastructure) directement. L'implémentation concrète est injectée au démarrage de l'application (composition root), jamais construite (`new PostgresOrderRepository()`) à l'intérieur d'un Use Case.

**Test décisif pour Copilot** : si un fichier dans `application/` ou `domain/` contient le mot-clé `new` suivi du nom d'une classe d'infrastructure (`new RedisClient()`, `new PostgresOrderRepository()`), c'est une violation à corriger immédiatement — l'injection doit se faire par le constructeur, jamais par instanciation directe.

---

## Checklist de revue rapide (à utiliser à chaque Pull Request, y compris générée par Copilot)

- [ ] Une classe = un fichier = une responsabilité claire, nommable en une phrase simple
- [ ] Aucun `import` de librairie technique dans `domain/`
- [ ] Toute nouvelle règle métier (langue, plateforme, type de détection) s'ajoute par **extension** (nouvelle classe), jamais par modification d'une classe existante testée
- [ ] Toute dépendance entre couches se fait via interface, jamais via classe concrète
- [ ] Aucune méthode qui lève `NotSupportedException` — signe qu'une interface est mal découpée
