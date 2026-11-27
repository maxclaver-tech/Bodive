"""Approved dashboard handoff. This module does not mutate Gumroad."""


def publication(dossier_id, dossier):
    return {
        "dossier_id": dossier_id,
        "product_markdown": dossier["product_markdown"], "listing": dossier["listing"],
        "procedure": [
            "Check originality, rights, title, price, and file against the approved package.",
            "Save product_markdown as workbook.md. In Gumroad Products, create a digital product.",
            "Upload workbook.md and enter the approved copy, price, and EUR currency.",
            "Confirm there is no upfront charge and the account terms match the approved plan.",
            "Publish once, then record the product URL. If publication is uncertain, inspect the dashboard.",
        ],
        "dashboard_docs": "https://gumroad.com/help/article/357-sell-an-ebook",
    }
