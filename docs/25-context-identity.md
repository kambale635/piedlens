# Bounded Context : Identity (comptes utilisateurs et comptes merchant)

## Rôle
Savoir **qui se connecte** (`User`) et **quel compte commercial existe** (`Merchant`). Identity ne gère jamais les droits : c'est le rôle d'Access Control (`20-context-access-control.md`).

## Agrégats

### User [AR]
| Attribut | Type |
|---|---|
| id | UserId [VO] |
| phoneNumber | PhoneNumber [VO] (E.164, unique globalement) |
| email | Email [VO]? |
| passwordHash | string (hash Django, jamais le mot de passe) |
| status | UserStatus [VO] (Active / Disabled) |
| createdAt | DateTime |

### Merchant [AR]
| Attribut | Type |
|---|---|
| id | MerchantId [VO] |
| ownerUserId | UserId [VO] (référence, pas l'objet) |
| name | string non vide |
| country / preferredLanguage / currency | CountryCode / LanguageCode / CurrencyCode [VO] (`currency` = devise principale, utilisée par INV-CRM-08) |
| subscriptionPlan | SubscriptionPlan [VO] (Starter / Pro / Agency) |
| createdAt | DateTime |

L'appartenance d'un `User` à un `Merchant` (Owner, Staff, agence) n'est **jamais** stockée dans Identity : elle s'exprime uniquement par un `RoleAssignment` scopé (INV-ID-06).

## Use Cases (contrats exacts dans `15-use-cases-catalog.md`)
- `RegisterUserUseCase` : route publique, crée le `User`, événement `UserRegistered`.
- `AuthenticateUserUseCase` : route publique, vérifie les identifiants, émet access + refresh token via le port `ITokenService`.
- `RefreshAccessTokenUseCase` : route publique, renouvelle l'access token.
- `CreateMerchantUseCase` : route authentifiée, crée le `Merchant`, événement `MerchantRegistered` (consommé par Access Control pour attribuer le rôle Owner).
- `ChangeSubscriptionPlanUseCase` : après confirmation de paiement.

## Flux d'inscription (chaque flèche = une transaction, un seul agrégat modifié)
```
RegisterUser → UserRegistered
Authenticate → tokens
CreateMerchant → MerchantRegistered
   └─ consommateur Access Control : AssignOwnerRoleOnMerchantRegisteredUseCase → RoleAssigned
```

## Ports
`IUserRepository`, `IMerchantRepository`, `IPasswordHasher`, `ITokenService`.

## Tests attendus
Unicité du téléphone, mot de passe jamais en clair ni dans les logs, erreur de connexion identique que le numéro existe ou non, downgrade refusé si l'usage dépasse le plan, `MerchantRegistered` écrit dans l'Outbox dans la même transaction que le `Merchant`.
