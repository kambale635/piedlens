# Standards de documentation & commentaires — niveau "framework publié"

> Objectif : que n'importe quel développeur (ou toi-même dans 6 mois) puisse ouvrir n'importe quel fichier et comprendre le "pourquoi", pas seulement le "quoi", sans consulter Slack ou une conversation passée. Un commentaire qui répète ce que le code dit déjà est inutile — un commentaire senior explique l'intention, l'invariant protégé, ou le piège évité.

## 1. Gabarit de docstring pour une classe de Domain (Aggregate Root / Entity)

```python
class Order:
    """Représente une commande détectée automatiquement à partir des messages d'un contact.

    Order est l'Aggregate Root du contexte Order Detection. Toute modification de son
    statut DOIT passer par `change_status()`, qui protège la machine à états définie
    dans docs/16-business-invariants-and-rules.md (INV-OD-01). Ne jamais modifier
    `self._status` directement, même depuis un autre fichier de ce même contexte.

    Invariants protégés par cette classe :
        - INV-OD-01 : transitions de statut valides uniquement
        - INV-OD-05 : le montant est toujours un objet Money, jamais un nombre nu

    Voir aussi :
        docs/11-context-order-detection.md pour le contexte fonctionnel complet
        docs/15-use-cases-catalog.md#DetectOrderUseCase pour le contrat d'entrée/sortie
    """
```

## 2. Gabarit de docstring pour un Use Case (Application layer)

```python
class DetectOrderUseCase:
    """Cas d'usage : détecte une nouvelle commande à partir d'un message évalué par le Rules Engine.

    Déclencheur : événement `MessageEvaluated` (consumer group order-detection-consumer)
    Référence complète : docs/15-use-cases-catalog.md#DetectOrderUseCase

    Args:
        evaluation_result: Résultat de l'évaluation du Rules Engine, contient le score
            de confiance et les données extraites (montant, devise, intention détectée).
        contact_id: Identifiant du contact source du message, utilisé pour la
            corrélation avec une commande existante (voir INV-OD-02, fenêtre de 3 jours).

    Returns:
        OrderDetectionResult: contient l'orderId créé/mis à jour et son statut.
        Si confidence_score < seuil configuré, le statut retourné est
        "needs_manual_validation" (voir INV-OD-04) — PAS une erreur, un cas normal.

    Raises:
        Aucune exception métier attendue en usage normal — les cas limites
        (score faible, commande ambiguë) sont des résultats, pas des erreurs.
    """
```

## 3. Gabarit pour une méthode qui protège un invariant précis

Toute méthode qui applique une règle métier référencée dans `16-business-invariants-and-rules.md` doit citer explicitement l'identifiant de la règle (`INV-XX-NN`) dans son docstring — jamais une règle métier sans référence traçable.

```python
def change_status(self, new_status: OrderStatus) -> None:
    """Change le statut de la commande en respectant la machine à états.

    Protège INV-OD-01 (docs/16-business-invariants-and-rules.md).

    Raises:
        InvalidOrderTransitionException: si la transition demandée n'est pas
            autorisée depuis le statut actuel (ex: paid_and_delivered -> pending_payment).
    """
    if not self._is_valid_transition(self._status, new_status):
        raise InvalidOrderTransitionException(self._status, new_status)
    ...
```

## 4. En-tête de fichier obligatoire pour chaque module d'infrastructure

```python
"""
Module: platform/event_bus/redis_stream_publisher.py
Contexte: transverse (platform), consommé par tous les bounded contexts
Rôle: implémentation technique unique de IEventPublisher, voir docs/14-event-driven-architecture.md

ATTENTION: ce fichier N'EST PAS appelé directement depuis un Use Case.
Seul le OutboxRelayWorker de chaque contexte publie réellement vers Redis
(voir INV-TR-02). Un appel direct depuis un Use Case est une violation
d'architecture à corriger immédiatement.
"""
```

## 5. Commentaires inline — quand et comment

- **Ne jamais commenter ce qui est évident** : `# incrémente x de 1` au-dessus de `x += 1` est interdit — bruit pur.
- **Toujours commenter un choix non évident** : pourquoi une valeur seuil précise, pourquoi une exception est avalée silencieusement, pourquoi un ordre d'opérations compte.
- **Format pour une décision non évidente** :
```python
# Pourquoi borné à ±10 points (INV-RE-03) : un merchant qui corrige 5 fois de suite
# par erreur de manipulation ne doit pas faire diverger le RuleSet global de façon
# disproportionnée. Voir historique de la décision : docs/13-technology-decision-adr.md
MAX_WEIGHT_ADJUSTMENT = 10
```

## 6. Documentation au niveau du module (README par bounded context)

Chaque app Django (bounded context) contient son propre `README.md` local avec :
- Rôle en une phrase
- Lien vers son fichier de contexte dans `/docs`
- Liste de ses Use Cases avec lien vers `15-use-cases-catalog.md`
- Commande pour lancer ses tests isolément

## 7. Règle pour Copilot (à ajouter à `06-copilot-instructions.md`, référence croisée)

Toute suggestion de classe, méthode publique, ou Use Case DOIT inclure un docstring suivant les gabarits ci-dessus. Une suggestion de code sans docstring sur une classe publique ou un Use Case est incomplète et doit être complétée avant d'être acceptée — pas de code "on documentera plus tard", jamais.

## 8. Format de commit (cohérence pour plusieurs comptes GitHub)

```
[context] type: description courte

Contexte: order-detection
Type: feat|fix|refactor|docs|test
Référence: docs/15-use-cases-catalog.md#DetectOrderUseCase (si applicable)

Corps optionnel expliquant le "pourquoi" si le changement touche
à un invariant métier (citer INV-XX-NN).
```
Exemple : `[order-detection] feat: implémente DetectOrderUseCase (INV-OD-01, INV-OD-04)`
