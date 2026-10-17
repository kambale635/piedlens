# Shared Kernel — Value Objects partagés entre tous les contextes

## Principe
Certains concepts (argent, téléphone, email, identifiants) apparaissent dans plusieurs bounded contexts. Plutôt que chaque contexte réinvente sa propre version (risque de divergence de validation entre contextes), ils sont définis **une seule fois** ici, dans un module `shared_kernel/`, importé (jamais dupliqué) par tous les contextes qui en ont besoin.

**Nuance DDD importante** : un Shared Kernel doit rester minimal — seulement des concepts vraiment universels et stables. On n'y met jamais une entité métier propre à un contexte (ex : `Order` reste exclusivement dans `order-detection`, il n'est jamais partagé directement — les autres contextes n'en connaissent qu'un identifiant `OrderId` ou des données dénormalisées via événement).

## Emplacement dans l'arborescence

```
/src/shared_kernel/
  /value-objects
    Money.py
    PhoneNumber.py
    Email.py
    CountryCode.py
    LanguageCode.py
    CurrencyCode.py
    ConfidenceScore.py
  /identifiers
    MerchantId.py
    UserId.py
    ContactId.py
    OrderId.py
    ...(un fichier par type d'identifiant, tous de simples wrappers UUID typés)
```

## Catalogue des Value Objects

### Money
```python
class Money:
    """Représente un montant monétaire, toujours associé à sa devise.

    Ne jamais manipuler un montant comme nombre nu ailleurs dans le code
    (voir INV-TR-05, docs/16-business-invariants-and-rules.md).

    Invariants :
        - amount >= 0 (pas de montant négatif — un remboursement est modélisé
          par un changement de statut d'Order, jamais par un Money négatif)
        - currency est un code ISO 4217 valide

    Raises:
        InvalidCurrencyException, NegativeAmountException
    """
    def add(self, other: "Money") -> "Money":
        """Additionne deux montants. Lève CurrencyMismatchException si les
        devises diffèrent — jamais de conversion implicite silencieuse."""
```

### PhoneNumber
Format E.164 obligatoire, validé à la construction. Utilisé par `Identity` (Merchant) et potentiellement `CRM` (Contact, si le numéro est disponible).

### Email
Validation de format standard à la construction. Utilisé par `Identity`.

### CountryCode / LanguageCode / CurrencyCode
Codes ISO stricts (3166-1 alpha-2 / 639-1 / 4217), validés à la construction contre une liste fermée — jamais une chaîne libre.

### ConfidenceScore
Borné [0, 100], utilisé par `Rules Engine` et `Order Detection`.

## Identifiants typés — pourquoi pas de simples UUID nus

```python
class OrderId:
    """Wrapper typé autour d'un UUID. Empêche de passer par erreur un
    ContactId là où un OrderId est attendu (le compilateur/type-checker
    lève une erreur, pas une erreur silencieuse en production)."""
    value: UUID
```
Chaque contexte définit son propre identifiant typé pour ses propres agrégats (`OrderId` dans `order-detection`, `ContactId` dans `crm`), mais leur **définition technique** (wrapper UUID) est mutualisée via une classe de base commune dans le shared kernel, pour éviter de dupliquer le même pattern 15 fois.

## Ce qui n'appartient PAS au Shared Kernel (limites strictes)

- Aucune logique métier (une méthode de validation complexe propre à un contexte reste dans ce contexte)
- Aucun agrégat ou entité (`Order`, `Contact`, `Merchant` restent dans leur contexte respectif)
- Aucune dépendance à Django/Redis/PostgreSQL — le shared kernel est aussi pur que le domaine de n'importe quel contexte (règle de dépendance identique, voir `01-architecture-overview.md`)
- `Permission` et `AccessScope` (contexte Access Control) : bien qu'utilisés transversalement, ils restent définis dans `access-control` et importés comme un **port** (`IPermissionChecker`), pas dupliqués dans le shared kernel — nuance : le shared kernel est pour des concepts de données universels, pas pour des ports de service.

## Règle pour Copilot

Avant de créer un nouveau Value Object dans un contexte, vérifier s'il existe déjà dans `shared_kernel/value-objects/`. Si un concept similaire existe dans 2 contextes avec une logique de validation différente, c'est un signal d'alerte — la divergence doit être discutée (pas silencieusement acceptée) avant de dupliquer.
