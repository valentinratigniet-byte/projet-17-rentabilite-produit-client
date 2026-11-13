# Note d'analyse — Rentabilité produit/client (ABC costing)

## 1. Méthode

Allocation ABC (Activity-Based Costing) simplifiée : trois pools de coûts
indirects, chacun rattaché à son véritable inducteur (cost driver) plutôt
qu'à une clé de répartition au prorata du CA :

| Pool | Inducteur | Coût |
|---|---|---:|
| Logistique (pick+pack+expédition) | nb de lignes de commande | 3,20 €/ligne |
| Traitement des paiements | montant réel × méthode réelle | 1,4 % (carte) / 2,9 % (PayPal) / 0,40 € fixe (virement) |
| SAV | nb de commandes, +surcoût si annulée | 1,80 €/commande, +9,00 € si annulée |

Le CA, les quantités, les méthodes de paiement et les commandes viennent
d'une requête directe sur la base du [Projet 07](https://github.com/valentinratigniet-byte/projet-07-base-ecommerce)
(2 000 produits, 5 000 clients). La marge brute (25 %, cohérente avec
l'hypothèse retenue au [Projet 16](https://github.com/valentinratigniet-byte/projet-16-business-case-investissement))
et les taux/coûts par inducteur sont des hypothèses — listées dans l'onglet
"Hypothèses" du rapport Excel, jamais mélangées avec le mesuré.

## 2. Résultat produit — un vrai signal, localisé

**9 produits sur 2000** ont une marge nette négative une fois la logistique
allouée, malgré une marge brute positive sur chacun. Le pire cas perd
**-29,0 %** de marge nette sur un produit vendu 2,54 € pièce, réparti sur
42 petites lignes de commande (5,93 €/ligne en moyenne) : le coût de
traitement (3,20 €/ligne) dépasse largement la marge brute générée par
ligne (25 % × 5,93 € = 1,48 €).

**Seuil de rentabilité approximatif : ~12,80 € de CA par ligne de commande**
(= coût logistique ÷ taux de marge brute). En dessous, une ligne coûte plus
cher à traiter qu'elle ne rapporte.

Une allocation naïve (coûts logistiques au prorata du CA) n'aurait **jamais**
révélé ce problème : ces 9 produits pèsent trop peu dans le CA total pour
apparaître dans un ratio global. L'ABC costing les isole précisément parce
qu'il regarde l'activité réelle (le nombre de lignes traitées), pas le CA.

**Mais l'ampleur reste modeste** : ~459 € de valeur détruite sur les 2 ans de commandes de la base (~230 €/an) pour ces 9
SKU, et les moyennes par catégorie restent stables entre 24,44 % et 24,50 %
de marge nette — ce n'est pas un problème de catalogue, c'est un problème de
9 SKU précis à traiter individuellement (revoir le prix, forcer un lot
minimum, ou les retirer du catalogue).

## 3. Résultat client — pas de segmentation trouvée, et c'est aussi une information

Le taux de marge nette par client est remarquablement homogène : du
1ᵉ au 99ᵉ centile, il varie entre **21,5 % et 24,2 %** (moyenne ~23 %). Le
nombre de commandes annulées par client (0 à 5) n'a qu'un effet marginal
(23,0 % en moyenne sans annulation, 22,1 % avec 4 annulations) — un écart
d'à peine 1 point.

**Conclusion honnête** : sur ce jeu de données, il n'y a pas de segment
client structurellement peu rentable à cibler. La distribution des
commandes par client est proche de l'uniforme (Faker attribue les commandes
sans logique comportementale), donc l'ABC costing ne trouve pas de signal
client à exploiter — contrairement au produit, où le prix catalogue crée un
vrai effet de seuil. Ce n'est pas un échec de la méthode : c'est le résultat
attendu d'une méthode appliquée honnêtement à des données sans biais
comportemental construit. Sur des données réelles (où le comportement
d'achat n'est pas uniforme), la même méthode révélerait probablement des
segments clients à faible marge nette — via, par exemple, un volume élevé de
petites commandes fréquentes chez certains clients.

## 4. Recommandations

1. **Produit** : traiter individuellement les 9 SKU à marge nette négative —
   augmenter le prix unitaire, imposer une quantité minimale de commande, ou
   les retirer du catalogue s'ils ne servent pas d'appel (produit d'appel
   assumé stratégiquement, auquel cas la perte est un choix, pas un oubli).
2. **Process** : industrialiser cette requête (vue SQL ou modèle dbt) pour la
   rejouer à chaque évolution du catalogue — le seuil de ~12,80 €/ligne est
   un radar simple à surveiller avant d'ajouter un nouveau SKU bas de gamme.
3. **Client** : ne pas construire de segmentation client sur ce jeu de
   données de simulation — la refaire directement sur des données réelles
   où le comportement d'achat porte un vrai signal.
