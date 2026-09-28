# Bounded Context : Rules Engine (le cœur adaptable)

## Rôle
Fournir un service **stateless et pur** (au sens fonctionnel autant que possible) qui évalue un message brut et retourne un score de confiance + des données extraites, sans jamais connaître d'où vient le message ni ce qui en sera fait ensuite. C'est le contexte qui garantit l'exigence "s'adapte à tout pays/langue/plateforme sans réécrire le code".

## Use Cases

### `EvaluateMessageUseCase`
**Entrée** : `MessageContent` (texte brut, présence de média, contexte de conversation récent), `MerchantId` (pour résoudre le bon RuleSet : global → pays → merchant, par ordre de priorité, le plus spécifique gagnant)
**Sortie** : `EvaluationResult` (score de confiance, règles déclenchées, données extraites : montant détecté, devise détectée, intention détectée)
**Orchestration** :
1. Résoudre le `RuleSet` applicable (fusion des règles globales + pays + merchant, les règles merchant-spécifiques surchargeant les règles pays, qui surchargent les règles globales)
2. Pour chaque `Rule` active, invoquer l'implémentation `IRuleEvaluator` correspondant à son `RuleType`
3. Agréger les scores pondérés (`ConfidenceScore`)
4. Publier `MessageEvaluated [EVT]` avec le résultat complet

## Stratégies d'évaluation (une classe par RuleType — Strategy Pattern, cohérent avec OCP)

| RuleType | Implémentation | Ce qu'elle détecte |
|---|---|---|
| KeywordMatch | `KeywordMatchEvaluator` | Présence de mots-clés (payé, reçu, combien, je prends...) dans la langue configurée |
| AmountPattern | `AmountPatternEvaluator` | Extraction d'un montant + devise à partir du format local (regex configurable par pays) |
| PaymentProofSignal | `MediaPresenceEvaluator` (MVP) puis `OcrPaymentProofEvaluator` (V2) | Présence d'une image ressemblant à un reçu/capture de transaction |
| EmojiSignal | `EmojiMatchEvaluator` | Émojis de confirmation (✅💰👍) |

## Structure de configuration des règles (exemple concret, table `RuleConfig`)

```json
{
  "scope": "country:CI",
  "language": "fr",
  "rules": [
    { "type": "KeywordMatch", "pattern": ["payé", "envoyé", "c'est fait", "c'est bon"], "weight": 40 },
    { "type": "AmountPattern", "pattern": "(\\d{1,3}([.,]?\\d{3})*)\\s?(F ?CFA|FCFA|F)", "weight": 30 },
    { "type": "EmojiSignal", "pattern": ["✅", "💰"], "weight": 15 }
  ]
}
```

**Ajouter un pays/langue = ajouter un bloc JSON comme celui-ci, sans toucher au code.** C'est la réponse concrète à "je ne veux rien de codé en dur".

## Interface exposée aux autres contextes

```
interface IRuleEvaluator {
  evaluate(message: MessageContent, ruleSet: RuleSet): EvaluationResult
}
```
Les contextes `order-detection` et `crm` ne consomment **que** cette interface (via le Use Case `EvaluateMessageUseCase`), jamais directement une des implémentations concrètes.

## Gestion des faux positifs (boucle de rétroaction)

Quand un merchant corrige manuellement une détection erronée (ex: une commande détectée à tort), l'événement `DetectionCorrectedByMerchant [EVT]` est publié. Le `Rules Engine` consomme cet événement pour ajuster localement le poids des règles pour CE merchant spécifiquement (RuleSet scope `merchant:{id}`), sans affecter les autres utilisateurs. C'est un apprentissage simple par ajustement de poids, pas du Machine Learning au MVP — suffisant et bien moins coûteux à opérer.

## Tests attendus (domaine pur, rapides, sans I/O)

- Chaque `IRuleEvaluator` testé isolément avec des cas réels multilingues (au moins français, anglais, + une langue locale prioritaire pour ton marché)
- Test de fusion de scope (global < pays < merchant) avec des règles contradictoires pour vérifier la priorité
- Test de non-régression : un corpus de vrais messages anonymisés (à constituer) pour vérifier que le taux de faux positifs reste sous un seuil acceptable à chaque changement de règle
