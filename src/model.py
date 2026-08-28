"""
Rentabilité produit/client — allocation ABC simplifiée (Activity-Based
Costing) : les coûts indirects sont répartis selon leur véritable inducteur
(cost driver), pas au prorata du chiffre d'affaires. Une allocation naïve
("chaque produit paie X% de ses coûts logistiques proportionnellement à son
CA") ne verrait jamais qu'un produit à 2,54 € vendu en 42 petites lignes de
commande coûte plus cher à traiter qu'il ne rapporte — l'ABC costing, si.

Trois pools de coûts indirects, chacun avec son propre inducteur :
  - Logistique (pick & pack & expédition)  -> nb de LIGNES de commande
  - Traitement des paiements                -> montant + méthode (frais réels par méthode)
  - Support / SAV                           -> nb de COMMANDES (surcoût si annulée)

Les volumes/CA/méthodes de paiement sont MESURÉS (requête sur le Projet 07).
La marge brute et les taux/coûts par inducteur sont des HYPOTHÈSES de gestion,
listées explicitement (même discipline que le Projet 16) — jamais mélangées
avec le mesuré.
"""
import os
from collections import defaultdict
from dataclasses import dataclass

import psycopg2

DSN = os.environ.get("DATABASE_URL",
                      "postgresql://portfolio:portfolio@127.0.0.1:5433/ecommerce")


@dataclass
class Assumptions:
    gross_margin_pct: float = 0.25          # cohérent avec l'hypothèse du Projet 16
    fulfillment_cost_per_line: float = 3.20  # €/ligne de commande (pick+pack+expédition)
    payment_fee_pct: dict = None             # % du montant, par méthode
    payment_fee_flat: dict = None            # € fixe, par méthode
    support_cost_per_order: float = 1.80     # €/commande (contact, suivi)
    support_cost_extra_cancelled: float = 9.00  # €/commande annulée, EN PLUS du coût de base

    def __post_init__(self):
        if self.payment_fee_pct is None:
            self.payment_fee_pct = {"card": 0.014, "paypal": 0.029}
        if self.payment_fee_flat is None:
            self.payment_fee_flat = {"transfer": 0.40}

    def payment_cost(self, method: str, amount: float) -> float:
        if method in self.payment_fee_pct:
            return amount * self.payment_fee_pct[method]
        return self.payment_fee_flat.get(method, 0.0)


def fetch_product_rows(cur):
    """Revenu/quantité/nb de lignes par produit, hors commandes annulées."""
    cur.execute("""
        SELECT p.id, p.name, c.name AS category,
               sum(oi.quantity) AS qty, sum(oi.quantity * oi.unit_price) AS revenue,
               count(*) AS nb_lines
        FROM order_item oi
        JOIN orders o ON o.id = oi.order_id
        JOIN product p ON p.id = oi.product_id
        JOIN category c ON c.id = p.category_id
        WHERE o.status <> 'cancelled'
        GROUP BY p.id, p.name, c.name
    """)
    return cur.fetchall()


def fetch_client_rows(cur):
    """Revenu/lignes/commandes par client (annulées incluses pour le SAV), hors annulées pour le CA."""
    cur.execute("""
        SELECT cu.id, cu.email,
               count(DISTINCT o.id) FILTER (WHERE o.status <> 'cancelled') AS nb_orders_ok,
               count(DISTINCT o.id) FILTER (WHERE o.status = 'cancelled') AS nb_orders_cancelled,
               count(oi.*) FILTER (WHERE o.status <> 'cancelled') AS nb_lines,
               coalesce(sum(oi.quantity * oi.unit_price) FILTER (WHERE o.status <> 'cancelled'), 0) AS revenue
        FROM customer cu
        JOIN orders o ON o.customer_id = cu.id
        LEFT JOIN order_item oi ON oi.order_id = o.id
        GROUP BY cu.id, cu.email
    """)
    return cur.fetchall()


def fetch_client_payments(cur):
    """Méthode + montant de chaque paiement, rattaché au client via la commande."""
    cur.execute("""
        SELECT o.customer_id, pay.method, pay.amount
        FROM payment pay
        JOIN orders o ON o.id = pay.order_id
    """)
    return cur.fetchall()


def product_margins(rows, a: Assumptions):
    out = []
    for pid, name, category, qty, revenue, nb_lines in rows:
        revenue = float(revenue)
        gross = revenue * a.gross_margin_pct
        fulfillment = nb_lines * a.fulfillment_cost_per_line
        out.append({"id": pid, "name": name, "category": category, "qty": int(qty),
                    "revenue": revenue, "nb_lines": nb_lines,
                    "gross_margin": gross, "fulfillment_cost": fulfillment,
                    "net_margin": gross - fulfillment})
    return out


def client_margins(client_rows, payment_rows, a: Assumptions):
    payment_cost_by_client = defaultdict(float)
    for customer_id, method, amount in payment_rows:
        payment_cost_by_client[customer_id] += a.payment_cost(method, float(amount))

    out = []
    for cid, email, nb_orders_ok, nb_cancelled, nb_lines, revenue in client_rows:
        revenue = float(revenue)
        gross = revenue * a.gross_margin_pct
        fulfillment = nb_lines * a.fulfillment_cost_per_line
        payment_cost = payment_cost_by_client.get(cid, 0.0)
        support = (nb_orders_ok + nb_cancelled) * a.support_cost_per_order \
            + nb_cancelled * a.support_cost_extra_cancelled
        out.append({"id": cid, "email": email, "revenue": revenue,
                    "nb_orders": nb_orders_ok, "nb_orders_cancelled": nb_cancelled,
                    "gross_margin": gross, "fulfillment_cost": fulfillment,
                    "payment_cost": payment_cost, "support_cost": support,
                    "net_margin": gross - fulfillment - payment_cost - support})
    return out


def self_check(cur, product_rows_out, client_rows_out, payment_rows):
    """Réconciliations — un chiffre publié doit boucler avec la base, pas juste 'sembler' juste."""
    cur.execute("""
        SELECT count(*), coalesce(sum(oi.quantity * oi.unit_price), 0)
        FROM order_item oi JOIN orders o ON o.id = oi.order_id
        WHERE o.status <> 'cancelled'
    """)
    total_lines_db, total_revenue_db = cur.fetchone()
    total_revenue_db = float(total_revenue_db)

    sum_lines_products = sum(p["nb_lines"] for p in product_rows_out)
    sum_revenue_products = sum(p["revenue"] for p in product_rows_out)
    sum_revenue_clients = sum(c["revenue"] for c in client_rows_out)

    assert sum_lines_products == total_lines_db, \
        f"Somme des lignes par produit ({sum_lines_products}) != total base ({total_lines_db})"
    assert abs(sum_revenue_products - total_revenue_db) < 0.01, \
        f"CA cumulé par produit ({sum_revenue_products:.2f}) != CA total base ({total_revenue_db:.2f})"
    assert abs(sum_revenue_clients - total_revenue_db) < 0.01, \
        f"CA cumulé par client ({sum_revenue_clients:.2f}) != CA total base ({total_revenue_db:.2f})"

    total_payment_amount_db = sum(float(amount) for _, _, amount in payment_rows)
    sum_payment_cost_clients = sum(c["payment_cost"] for c in client_rows_out)
    # Le coût de paiement alloué doit rester cohérent avec le volume réel traité
    # (borne large : entre le tarif flat le plus bas et le taux % le plus haut).
    assert 0 <= sum_payment_cost_clients <= total_payment_amount_db * 0.03, \
        "Coût de paiement alloué hors bornes plausibles vs volume réel traité"


def run(a: Assumptions = None):
    a = a or Assumptions()
    conn = psycopg2.connect(DSN); cur = conn.cursor()
    product_rows = fetch_product_rows(cur)
    client_rows = fetch_client_rows(cur)
    payment_rows = fetch_client_payments(cur)

    products = product_margins(product_rows, a)
    clients = client_margins(client_rows, payment_rows, a)
    self_check(cur, products, clients, payment_rows)

    cur.close(); conn.close()
    return products, clients, a


if __name__ == "__main__":
    products, clients, a = run()
    neg_products = [p for p in products if p["net_margin"] < 0]
    neg_clients = [c for c in clients if c["net_margin"] < 0]
    print(f"{len(products)} produits analysés, {len(neg_products)} à marge nette négative "
          f"({sum(-p['net_margin'] for p in neg_products):,.0f} € de valeur détruite/an)")
    print(f"{len(clients)} clients analysés, {len(neg_clients)} à marge nette négative "
          f"({sum(-c['net_margin'] for c in neg_clients):,.0f} € de valeur détruite/an)")
