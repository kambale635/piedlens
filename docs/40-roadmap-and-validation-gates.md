Les décisions D1 à D8 et les règles T1 à T10 du prompt d'implémentation prévalent sur les docs 30 à 39 en cas de différence.

Décisions persistées : [`41-implementation-decisions.md`](41-implementation-decisions.md).

# Roadmap Afrique et portes de validation

Les phases s'exécutent dans l'ordre; B et C ne commencent qu'après lecture et décision documentée sur les résultats du pilote A. Aucun adaptateur réel ne s'active sans autorisation, credentials enregistrés en doc 28 et revue juridique locale.

| Phase | Périmètre | Porte de sortie |
|---|---|---|
| A — pilote RDC | Mode sans API : import/collage consentis; pack RDC; taux saisis par vendeur + `RateSnapshot`; analyse configurable de SMS Mobile Money et instructions manuelles; assistant de négociation avec validation vendeur; Status Studio, attribution et mini-boutique lecture seule | 10 vendeurs actifs et consentants; mesurer activation, qualité extraction, corrections, taux de paiement rapproché, usage hebdo, incidents/confidentialité, compréhension des instructions; revue juridique RDC et approbation de chaque vendeur. Seuils chiffrés à fixer avant recrutement; ne pas inventer un résultat cible après coup. |
| B — opération | Catalogue/variantes/stock append-only; livraison par zones avec code de remise; profils et vérification fournisseur revue par personnel | décision après pilote A; préciser responsables opérationnels, support, abus, coûts, rétention documents et tests de sécurité avant déploiement |
| C — intégrations et expansion | Agrégateurs Mobile Money réels; bons de commande et paiement fournisseur via prestataire agréé; packs autres pays | décision après A (et résultats B si B réalisé); contrats/licences, accords, sandbox, tests de sécurité, plan d'incident, support et credentials validés |

## Invariants de lancement

- Mode mock/manual par défaut; aucune transaction financière réelle ni promesse d'API tant qu'elle n'est pas vérifiée.
- Configuration versionnée et réversible; consentement, minimisation, audit et suppression testés.
- Préparer les seuils du pilote avant le premier vendeur : critères d'activation, conversion, précision des suggestions, plaintes, incidents et support. Arrêter/ajuster si sécurité, conformité ou confiance est compromise.
- Conditions juridiques à signer : paiements/agrégation, KYC/AML, données personnelles/transfrontalières, protection consommateur, livreurs, fournisseurs, contenus/Meta et fiscalité RDC.

## Tests/évidence par porte

Phase A : tests d'import/consentement/suppression, règles fr/en et locale natives validées, taux snapshot/arrondi, duplicate transaction ID, vendeur approuve contre-offre, aucun envoi/status automatique, attribution sans PII, mini-boutique publique sans données privées, audit/logs sans contenu.
Phase B : invariants ledger, concurrence stock, code anti-bruteforce, rapprochement reversement, revue d'identité et accès document chiffré.
Phase C : sandbox fournisseur, signatures anti-rejeu, idempotence, rapprochement et gestion d'incident; preuves d'agrément et contrat avant live.

## Décision et extension

Registre par phase : hypothèse, échantillon, résultat, incidents, coûts, objections vendeurs, décision `go / revise / stop`, responsable et date. Pack pays et adaptateurs restent désactivables. Aucun démarrage B/C par calendrier seul; la décision dépend des résultats documentés du pilote de 10 vendeurs.
