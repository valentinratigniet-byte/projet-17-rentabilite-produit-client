"""
Génère le dossier de rentabilité produit/client (Excel) : synthèse,
top/bottom produits, rollup catégorie, top/bottom clients, hypothèses.

Usage : python src/report.py
"""
from collections import defaultdict
from datetime import date
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from model import Assumptions, run

OUT = Path(__file__).resolve().parent.parent / "output"

PETROL = "137A8B"; PETROL_D = "0C5563"
GREEN = "2FA36B"; RED = "D9534F"
EURO = '#,##0" €"'
thin = Side(style="thin", color="DCE2E8")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)
HEAD_FILL = PatternFill("solid", fgColor=PETROL)
HEAD_FONT = Font(bold=True, color="FFFFFF")


def header_row(ws, row, headers, start=1):
    for i, h in enumerate(headers):
        c = ws.cell(row=row, column=start + i, value=h)
        c.fill = HEAD_FILL; c.font = HEAD_FONT; c.border = BORDER
        c.alignment = Alignment(horizontal="center")


def category_rollup(products):
    cat = defaultdict(lambda: {"revenue": 0.0, "net_margin": 0.0, "n": 0})
    for p in products:
        c = cat[p["category"]]
        c["revenue"] += p["revenue"]; c["net_margin"] += p["net_margin"]; c["n"] += 1
    return cat


def build(products, clients, a, path):
    wb = Workbook()

    ws = wb.active; ws.title = "Synthèse"; ws.sheet_view.showGridLines = False
    ws["B2"] = "Rentabilité produit / client — allocation ABC"
    ws["B2"].font = Font(bold=True, size=16, color=PETROL_D)
    ws["B3"] = f"Généré automatiquement le {date.today().isoformat()}"
    ws["B3"].font = Font(italic=True, color="5E6B7A")

    neg_p = [p for p in products if p["net_margin"] < 0]
    neg_c = [c for c in clients if c["net_margin"] < 0]
    total_revenue = sum(p["revenue"] for p in products)
    total_net = sum(p["net_margin"] for p in products)
    cards = [("CA analysé", total_revenue, EURO),
             ("Marge nette globale", total_net / total_revenue, '0.0%'),
             ("Produits à marge nette négative", len(neg_p), '#,##0" / ' + f'{len(products)}"'),
             ("Clients à marge nette négative", len(neg_c), '#,##0" / ' + f'{len(clients)}"')]
    for i, (label, val, fmt) in enumerate(cards):
        col = 2 + i * 2
        lc = ws.cell(row=5, column=col, value=label)
        lc.font = Font(bold=True, color="5E6B7A", size=9)
        vc = ws.cell(row=6, column=col, value=val)
        vc.font = Font(bold=True, size=15, color=PETROL)
        vc.number_format = fmt
        ws.merge_cells(start_row=5, start_column=col, end_row=5, end_column=col + 1)
        ws.merge_cells(start_row=6, start_column=col, end_row=6, end_column=col + 1)
    for col in range(2, 12):
        ws.column_dimensions[get_column_letter(col)].width = 17

    ws["B9"] = ("Constat : la marge nette est homogène par catégorie (~24,4-24,5 %) — le problème n'est "
                "pas une catégorie entière, mais un petit nombre de SKU pris individuellement. Voir "
                "docs/analyse.md pour la lecture complète.")
    ws["B9"].alignment = Alignment(wrap_text=True); ws.row_dimensions[9].height = 30
    ws.merge_cells("B9:K9")

    ws_p = wb.create_sheet("Produits (pire -> meilleur)"); ws_p.sheet_view.showGridLines = False
    header_row(ws_p, 1, ["Produit", "Catégorie", "CA €", "Lignes", "Marge brute €",
                          "Coût logistique €", "Marge nette €", "Taux marge nette"])
    products_sorted = sorted(products, key=lambda p: p["net_margin"] / p["revenue"] if p["revenue"] else 0)
    show = products_sorted[:20] + products_sorted[-10:]
    for r, p in enumerate(show, start=2):
        rate = p["net_margin"] / p["revenue"] if p["revenue"] else 0
        ws_p.cell(row=r, column=1, value=p["name"]).border = BORDER
        ws_p.cell(row=r, column=2, value=p["category"]).border = BORDER
        for col, val, fmt in [(3, p["revenue"], EURO), (4, p["nb_lines"], '#,##0'),
                               (5, p["gross_margin"], EURO), (6, p["fulfillment_cost"], EURO),
                               (7, p["net_margin"], EURO), (8, rate, '+0.0%;-0.0%')]:
            cell = ws_p.cell(row=r, column=col, value=round(val, 4) if col == 8 else round(val))
            cell.number_format = fmt; cell.border = BORDER
    ws_p.column_dimensions["A"].width = 36; ws_p.column_dimensions["B"].width = 16
    for col in "CDEFGH":
        ws_p.column_dimensions[col].width = 15
    ws_p.conditional_formatting.add(
        f"H2:H{len(show)+1}",
        ColorScaleRule(start_type="min", start_color=RED, mid_type="num", mid_value=0, mid_color="FFFFFF",
                        end_type="max", end_color=GREEN))

    ws_c = wb.create_sheet("Par catégorie"); ws_c.sheet_view.showGridLines = False
    header_row(ws_c, 1, ["Catégorie", "Nb produits", "CA €", "Marge nette €", "Taux marge nette"])
    cat = category_rollup(products)
    cats_sorted = sorted(cat.items(), key=lambda kv: kv[1]["net_margin"] / kv[1]["revenue"])
    for r, (name, c) in enumerate(cats_sorted, start=2):
        rate = c["net_margin"] / c["revenue"]
        ws_c.cell(row=r, column=1, value=name).border = BORDER
        ws_c.cell(row=r, column=2, value=c["n"]).border = BORDER
        c1 = ws_c.cell(row=r, column=3, value=round(c["revenue"])); c1.number_format = EURO; c1.border = BORDER
        c2 = ws_c.cell(row=r, column=4, value=round(c["net_margin"])); c2.number_format = EURO; c2.border = BORDER
        c3 = ws_c.cell(row=r, column=5, value=round(rate, 4)); c3.number_format = '0.00%'; c3.border = BORDER
    ws_c.column_dimensions["A"].width = 20
    for col in "BCDE":
        ws_c.column_dimensions[col].width = 15

    ws_cl = wb.create_sheet("Clients (pire -> meilleur)"); ws_cl.sheet_view.showGridLines = False
    header_row(ws_cl, 1, ["Client", "CA €", "Commandes", "Annulées", "Marge brute €",
                           "Logistique €", "Paiement €", "SAV €", "Marge nette €", "Taux marge nette"])
    clients_sorted = sorted(clients, key=lambda c: c["net_margin"] / c["revenue"] if c["revenue"] else 0)
    show_c = [c for c in clients_sorted if c["revenue"] > 0][:20]
    for r, c in enumerate(show_c, start=2):
        rate = c["net_margin"] / c["revenue"] if c["revenue"] else 0
        ws_cl.cell(row=r, column=1, value=c["email"]).border = BORDER
        for col, val, fmt in [(2, c["revenue"], EURO), (3, c["nb_orders"], '#,##0'),
                               (4, c["nb_orders_cancelled"], '#,##0'), (5, c["gross_margin"], EURO),
                               (6, c["fulfillment_cost"], EURO), (7, c["payment_cost"], EURO),
                               (8, c["support_cost"], EURO), (9, c["net_margin"], EURO),
                               (10, rate, '+0.0%;-0.0%')]:
            cell = ws_cl.cell(row=r, column=col, value=round(val, 4) if col == 10 else round(val))
            cell.number_format = fmt; cell.border = BORDER
    ws_cl.column_dimensions["A"].width = 30
    for col in "BCDEFGHIJ":
        ws_cl.column_dimensions[col].width = 13

    ws_h = wb.create_sheet("Hypothèses"); ws_h.sheet_view.showGridLines = False
    header_row(ws_h, 1, ["Hypothèse", "Valeur", "Origine"])
    rows = [
        ("Marge brute", f"{a.gross_margin_pct:.0%}", "Hypothèse (cohérente avec le Projet 16)"),
        ("Coût logistique / ligne de commande", f"{a.fulfillment_cost_per_line:.2f} €", "Hypothèse (pick+pack+expédition)"),
        ("Frais paiement carte", f"{a.payment_fee_pct['card']:.1%} du montant", "Hypothèse (taux processeur typique)"),
        ("Frais paiement PayPal", f"{a.payment_fee_pct['paypal']:.1%} du montant", "Hypothèse (taux processeur typique)"),
        ("Frais paiement virement", f"{a.payment_fee_flat['transfer']:.2f} € fixe", "Hypothèse"),
        ("Coût SAV / commande", f"{a.support_cost_per_order:.2f} €", "Hypothèse"),
        ("Surcoût SAV / commande annulée", f"{a.support_cost_extra_cancelled:.2f} € (en plus)", "Hypothèse — cohérent avec le taux d'annulation mesuré au Projet 16"),
        ("Nb produits / clients analysés", f"{len(products)} / {len(clients)}", "Mesuré (Projet 07)"),
    ]
    for r, (label, val, origin) in enumerate(rows, start=2):
        ws_h.cell(row=r, column=1, value=label).border = BORDER
        ws_h.cell(row=r, column=2, value=val).border = BORDER
        ws_h.cell(row=r, column=3, value=origin).border = BORDER
    ws_h.column_dimensions["A"].width = 34; ws_h.column_dimensions["B"].width = 22; ws_h.column_dimensions["C"].width = 50

    wb.save(path)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    products, clients, a = run()
    path = OUT / f"rentabilite_{date.today().isoformat()}.xlsx"
    build(products, clients, a, path)
    neg_p = [p for p in products if p["net_margin"] < 0]
    print(f"Rapport généré : {path.name}")
    print(f"  {len(neg_p)}/{len(products)} produits à marge nette négative "
          f"({sum(-p['net_margin'] for p in neg_p):,.0f} € de valeur détruite sur les 2 ans de commandes)")


if __name__ == "__main__":
    main()
