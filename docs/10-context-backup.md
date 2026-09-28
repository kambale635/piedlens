# Bounded Context : Backup (sauvegarde automatique)

## Rôle
Garantir qu'aucune donnée client (messages, contacts, historique) n'est jamais perdue même en cas de bannissement, suppression ou piratage du compte plateforme du merchant.

## Use Cases

### `CreateDailySnapshotUseCase`
Déclenché par un job planifié (quotidien pour plan Starter, temps réel/incrémental pour plan Pro+).
1. Récupérer tous les nouveaux `Message` et `Contact` depuis le dernier snapshot réussi
2. Calculer le `dataIntegrityHash` (hash cryptographique du contenu, pour preuve d'intégrité en cas de litige futur)
3. Persister via `IBackupRepository` + stocker les médias via `IObjectStorage`
4. Publier `BackupCompleted [EVT]` ou `BackupFailed [EVT]`

### `RestoreFromSnapshotUseCase`
1. Récupérer le dernier snapshot réussi (ou un snapshot précis à une date donnée)
2. Générer un export dans 2 formats : lisible humain (PDF/CSV) et ré-importable (JSON structuré)
3. Retourner une URL de téléchargement temporaire (signée, expirant après X heures)

### `CheckAccountHealthUseCase`
Déclenché périodiquement, utilise `IAccountHealthChecker` (contexte Platform Connectors) pour détecter des signaux avant-coureurs de bannissement, et déclenche une alerte préventive au merchant si un signal est détecté.

## Interfaces (ports)

```
interface IBackupRepository {
  save(snapshot: BackupSnapshot): void
  findLatestSuccessful(platformConnectionId: PlatformConnectionId): BackupSnapshot | null
  findByDateRange(platformConnectionId: PlatformConnectionId, from: DateTime, to: DateTime): BackupSnapshot[]
}

interface IObjectStorage {
  store(file: MediaFile): StorageReference
  retrieve(reference: StorageReference): MediaFile
  generateSignedUrl(reference: StorageReference, expiresInMinutes: number): string
}
```

## Règle métier importante : sauvegarde incrémentale, pas totale à chaque fois

Pour maîtriser les coûts de stockage (exigence de prix bas du produit), chaque snapshot après le premier est **incrémental** — seuls les nouveaux messages/contacts depuis le dernier snapshot réussi sont ajoutés. La restauration reconstitue l'état complet en rejouant la chaîne de snapshots incrémentaux jusqu'à la date demandée. (Pattern proche de l'Event Sourcing, sans en adopter toute la complexité au MVP.)

## Consentement et conformité

- Un merchant doit donner un consentement explicite (`consentGivenAt` sur `PlatformConnection`) avant toute sauvegarde des données de SES clients — bonne pratique même hors zone UE, argument de confiance commercial fort.
- Droit à l'oubli : `DeleteAllMerchantDataUseCase` doit exister dès le MVP — supprime les snapshots, les médias associés, et publie `MerchantDataDeleted [EVT]` consommé par tous les autres contextes pour purger leurs propres données liées.

## Cas limites à couvrir

- Échec partiel d'un snapshot (ex : coupure réseau à mi-parcours) → le snapshot doit être marqué `Failed`, jamais un snapshot partiel marqué `Succeeded` (intégrité avant tout)
- Merchant qui change de numéro de téléphone / migre de compte → procédure de rattachement du nouvel `externalAccountId` à l'historique existant sans perte
- Volume important (merchant avec des années d'historique à la première connexion) → traitement de l'import initial en tâche de fond asynchrone avec suivi de progression, jamais une requête synchrone bloquante

## Tests attendus

- Test d'intégrité : un snapshot restauré doit produire un hash identique au hash calculé à la sauvegarde
- Test d'incrémentalité : vérifier qu'un deuxième snapshot ne duplique pas les données du premier
- Test du parcours complet restauration (snapshot → export → URL signée → téléchargement)
